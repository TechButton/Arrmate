"""SQLite user database for multi-user authentication."""

import hashlib
import json
import logging
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator

import bcrypt as _bcrypt

logger = logging.getLogger(__name__)

VALID_ROLES = ("admin", "power_user", "user")


def _db_path() -> Path:
    from ..config.settings import settings
    return Path(settings.auth_data_dir) / "users.db"


def _auth_json_path() -> Path:
    from ..config.settings import settings
    return Path(settings.auth_data_dir) / "auth.json"


@contextmanager
def _get_conn() -> Generator[sqlite3.Connection, None, None]:
    """Get a database connection with row_factory."""
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return secrets.token_hex(16)


_db_ready = False


def _ensure_db() -> None:
    """Call init_db() once if not already done (lazy init for resilience)."""
    global _db_ready
    if not _db_ready:
        init_db()
        _db_ready = True


def init_db() -> None:
    """Initialize the database tables and migrate from auth.json if needed."""
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                invited_by TEXT,
                must_change_password INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS invites (
                token TEXT PRIMARY KEY,
                role TEXT NOT NULL DEFAULT 'user',
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                used_by TEXT,
                used_at TEXT
            );

            CREATE TABLE IF NOT EXISTS media_requests (
                id TEXT PRIMARY KEY,
                request_type TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                title TEXT NOT NULL,
                details TEXT,
                media_type TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                resolved_by TEXT,
                resolver_notes TEXT
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                message TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'info',
                read INTEGER NOT NULL DEFAULT 0,
                request_id TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS api_tokens (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                token_hash TEXT UNIQUE NOT NULL,
                token_prefix TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                expires_at TEXT,
                enabled INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.commit()

        # Migrations: add columns that may not exist in older databases
        for _migration_sql in [
            "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN plex_id TEXT",
            "ALTER TABLE users ADD COLUMN auth_provider TEXT NOT NULL DEFAULT 'local'",
            "ALTER TABLE media_requests ADD COLUMN notified_queued INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE media_requests ADD COLUMN notified_imported INTEGER NOT NULL DEFAULT 0",
        ]:
            try:
                conn.execute(_migration_sql)
                conn.commit()
            except Exception:
                pass  # Column already exists

        # Unique index for plex_id (only on non-NULL rows)
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_plex_id "
                "ON users (plex_id) WHERE plex_id IS NOT NULL"
            )
            conn.commit()
        except Exception:
            pass

        # Migrate from auth.json if no users exist
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    if count == 0:
        _migrate_from_auth_json()

    # If still no users (no auth.json either), create default admin account
    with _get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        _create_default_admin()


def _create_default_admin() -> None:
    """Create the default admin/changeme123 account on fresh installs."""
    try:
        password_hash = _bcrypt.hashpw(b"changeme123", _bcrypt.gensalt()).decode()
        with _get_conn() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO users
                   (id, username, password_hash, role, enabled, created_at, must_change_password)
                   VALUES (?, 'admin', ?, 'admin', 1, ?, 1)""",
                (_new_id(), password_hash, _now()),
            )
            conn.commit()
        logger.info("Created default admin account (username: admin) — change password on first login")
    except Exception as e:
        logger.warning("Failed to create default admin: %s", e)


def _migrate_from_auth_json() -> None:
    """If auth.json exists with credentials, import as admin user."""
    auth_json = _auth_json_path()
    if not auth_json.exists():
        return
    try:
        data = json.loads(auth_json.read_text())
        username = data.get("username")
        password_hash = data.get("password_hash")
        if not username or not password_hash:
            return

        with _get_conn() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO users
                   (id, username, password_hash, role, enabled, created_at)
                   VALUES (?, ?, ?, 'admin', 1, ?)""",
                (_new_id(), username, password_hash, _now()),
            )
            conn.commit()
        logger.info("Migrated auth.json user '%s' as admin", username)
    except Exception as e:
        logger.warning("Failed to migrate auth.json: %s", e)


# ===== User CRUD =====

def create_user(
    username: str,
    password: str,
    role: str = "user",
    invited_by: str | None = None,
) -> dict | None:
    """Create a new user. Returns user dict or None if username taken."""
    _ensure_db()
    if role not in VALID_ROLES:
        role = "user"
    user_id = _new_id()
    password_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
    try:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO users
                   (id, username, password_hash, role, enabled, created_at, invited_by)
                   VALUES (?, ?, ?, ?, 1, ?, ?)""",
                (user_id, username, password_hash, role, _now(), invited_by),
            )
            conn.commit()
        return get_user_by_id(user_id)
    except sqlite3.IntegrityError:
        return None


def get_user_by_id(user_id: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_username(username: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None


def verify_user(username: str, password: str) -> dict | None:
    """Verify credentials. Returns user dict or None if invalid/disabled.

    Plex SSO users (auth_provider='plex') have no local password and will
    always return None here — they must log in via the Plex SSO flow.
    """
    user = get_user_by_username(username)
    if not user or not user.get("enabled"):
        return None
    if user.get("auth_provider") == "plex":
        return None  # Plex users cannot log in with a local password
    try:
        if _bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            return user
    except Exception:
        pass
    return None


def list_users() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM users ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]


def update_user(user_id: str, **kwargs) -> bool:
    """Update user fields (role, enabled, email). Returns True if updated."""
    allowed = {"role", "enabled", "email"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    # Keys are filtered to the allowlist above before being interpolated.
    # Values are always passed as parameters — no injection risk.
    set_clause = ", ".join(f"{k} = ?" for k in updates)  # nosec B608
    values = list(updates.values()) + [user_id]
    with _get_conn() as conn:
        cursor = conn.execute(
            f"UPDATE users SET {set_clause} WHERE id = ?", values  # nosec B608
        )
        conn.commit()
        return cursor.rowcount > 0


def change_password(user_id: str, new_password: str) -> bool:
    """Change a user's password and clear must_change_password flag. Returns True on success."""
    password_hash = _bcrypt.hashpw(new_password.encode(), _bcrypt.gensalt()).decode()
    with _get_conn() as conn:
        cursor = conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
            (password_hash, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_user(user_id: str) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_user_by_plex_id(plex_id: str) -> dict | None:
    """Look up a user by their Plex UUID. Returns None if not found."""
    _ensure_db()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE plex_id = ?", (plex_id,)
        ).fetchone()
        return dict(row) if row else None


def create_plex_user(
    plex_id: str,
    username: str,
    email: str | None,
    role: str = "user",
) -> dict | None:
    """Create a user whose identity comes from Plex (no local password).

    Uses a sentinel password hash ("!plex") that bcrypt will never produce,
    so these accounts are unreachable via the normal password login path.

    Returns the user dict or None if the username is already taken.
    """
    if role not in VALID_ROLES:
        role = "user"
    user_id = _new_id()
    # "!plex" is not a valid bcrypt hash — verify_user() will short-circuit
    # on auth_provider == 'plex' before bcrypt is ever called.
    placeholder_hash = "!plex"
    try:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO users
                   (id, username, email, password_hash, role, enabled, created_at,
                    plex_id, auth_provider)
                   VALUES (?, ?, ?, ?, ?, 1, ?, ?, 'plex')""",
                (user_id, username, email, placeholder_hash, role, _now(), plex_id),
            )
            conn.commit()
        return get_user_by_id(user_id)
    except sqlite3.IntegrityError:
        return None


def has_any_users() -> bool:
    try:
        _ensure_db()
        with _get_conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            return count > 0
    except Exception:
        return False


# ===== Invites =====

def create_invite(role: str, created_by: str, ttl_hours: int = 48) -> str:
    """Create an invite token. Returns the token string."""
    if role not in VALID_ROLES:
        role = "user"
    token = secrets.token_urlsafe(32)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    ).isoformat()
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO invites
               (token, role, created_by, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?)""",
            (token, role, created_by, _now(), expires_at),
        )
        conn.commit()
    return token


def get_invite(token: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM invites WHERE token = ?", (token,)
        ).fetchone()
        return dict(row) if row else None


def validate_invite(token: str) -> dict | None:
    """Return invite if valid (not used, not expired). None otherwise."""
    invite = get_invite(token)
    if not invite:
        return None
    if invite["used"]:
        return None
    expires_at = datetime.fromisoformat(invite["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        return None
    return invite


def use_invite(token: str, username: str, password: str) -> dict | None:
    """Use an invite to create a user. Returns user dict or None on failure."""
    invite = validate_invite(token)
    if not invite:
        return None
    user = create_user(
        username, password,
        role=invite["role"],
        invited_by=invite["created_by"],
    )
    if not user:
        return None
    with _get_conn() as conn:
        conn.execute(
            "UPDATE invites SET used = 1, used_by = ?, used_at = ? WHERE token = ?",
            (user["id"], _now(), token),
        )
        conn.commit()
    return user


def list_invites(include_used: bool = False) -> list[dict]:
    with _get_conn() as conn:
        if include_used:
            rows = conn.execute(
                "SELECT * FROM invites ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM invites WHERE used = 0 ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def delete_invite(token: str) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute("DELETE FROM invites WHERE token = ?", (token,))
        conn.commit()
        return cursor.rowcount > 0


# ===== Media Requests =====

def get_trackable_requests() -> list[dict]:
    """Return open requests that haven't been fully notified yet."""
    try:
        _ensure_db()
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM media_requests
                   WHERE status NOT IN ('rejected')
                     AND notified_imported = 0
                   ORDER BY created_at DESC"""
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def mark_request_queued(req_id: str) -> bool:
    """Set notified_queued=1 for a request. Returns True if updated."""
    with _get_conn() as conn:
        cursor = conn.execute(
            "UPDATE media_requests SET notified_queued = 1 WHERE id = ?", (req_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


def mark_request_imported(req_id: str) -> bool:
    """Set notified_imported=1, status=completed, resolved_at=now. Returns True if updated."""
    with _get_conn() as conn:
        cursor = conn.execute(
            """UPDATE media_requests
               SET notified_imported = 1, status = 'completed', resolved_at = ?
               WHERE id = ?""",
            (_now(), req_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def create_request(
    request_type: str,
    user_id: str,
    title: str,
    details: str = "",
    media_type: str = "",
) -> dict:
    req_id = _new_id()
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO media_requests
               (id, request_type, requested_by, title, details, media_type, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (req_id, request_type, user_id, title, details, media_type, _now()),
        )
        conn.commit()
    return get_request(req_id)


def get_request(req_id: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM media_requests WHERE id = ?", (req_id,)
        ).fetchone()
        return dict(row) if row else None


def list_requests(
    user_id: str | None = None,
    status: str | None = None,
) -> list[dict]:
    query = "SELECT * FROM media_requests WHERE 1=1"
    params: list = []
    if user_id:
        query += " AND requested_by = ?"
        params.append(user_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    with _get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def update_request(
    req_id: str,
    status: str,
    resolved_by: str,
    notes: str = "",
) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute(
            """UPDATE media_requests
               SET status = ?, resolved_at = ?, resolved_by = ?, resolver_notes = ?
               WHERE id = ?""",
            (status, _now(), resolved_by, notes, req_id),
        )
        conn.commit()
        return cursor.rowcount > 0


# ===== Notifications =====

def create_notification(
    user_id: str,
    message: str,
    type: str = "info",
    request_id: str | None = None,
) -> dict:
    notif_id = _new_id()
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO notifications
               (id, user_id, message, type, read, request_id, created_at)
               VALUES (?, ?, ?, ?, 0, ?, ?)""",
            (notif_id, user_id, message, type, request_id, _now()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM notifications WHERE id = ?", (notif_id,)
        ).fetchone()
        return dict(row) if row else {}


def get_unread_count(user_id: str) -> int:
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read = 0",
                (user_id,),
            ).fetchone()
            return row[0]
    except Exception:
        return 0


def get_notifications(user_id: str, limit: int = 20) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM notifications
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_notifications_read(user_id: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            "UPDATE notifications SET read = 1 WHERE user_id = ?", (user_id,)
        )
        conn.commit()


def get_admin_and_power_user_ids() -> list[str]:
    """Return IDs for all active admins and power users (for notification dispatch)."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT id FROM users WHERE role IN ('admin', 'power_user') AND enabled = 1"
            ).fetchall()
            return [r[0] for r in rows]
    except Exception:
        return []


# ===== API Tokens =====

def _hash_token(plain_token: str) -> str:
    return hashlib.sha256(plain_token.encode()).hexdigest()


def create_api_token(
    user_id: str,
    name: str,
    expires_days: int | None = None,
) -> tuple[str, str]:
    """Create an API token for a user.

    Returns (token_id, plain_token). The plain token is only available at
    creation time — store it immediately, it cannot be recovered later.
    """
    _ensure_db()
    plain_token = "amt_" + secrets.token_urlsafe(32)
    token_hash = _hash_token(plain_token)
    token_prefix = plain_token[:12]  # "amt_XXXXXXXX" — safe to display
    token_id = _new_id()
    expires_at = None
    if expires_days:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_days)).isoformat()
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO api_tokens
               (id, user_id, name, token_hash, token_prefix, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (token_id, user_id, name, token_hash, token_prefix, _now(), expires_at),
        )
        conn.commit()
    return token_id, plain_token


def validate_api_token(plain_token: str) -> dict | None:
    """Validate a Bearer token.

    Returns a user-like dict {user_id, username, role, token_id} on success,
    or None if the token is invalid, disabled, or expired.
    Also updates last_used_at on every successful validation.
    """
    try:
        token_hash = _hash_token(plain_token)
        with _get_conn() as conn:
            row = conn.execute(
                """SELECT t.id AS token_id, t.enabled AS token_enabled, t.expires_at,
                          u.id AS user_id, u.username, u.role, u.enabled AS user_enabled
                   FROM api_tokens t
                   JOIN users u ON t.user_id = u.id
                   WHERE t.token_hash = ?""",
                (token_hash,),
            ).fetchone()
            if not row:
                return None
            row = dict(row)
            if not row["token_enabled"] or not row["user_enabled"]:
                return None
            if row["expires_at"]:
                exp = datetime.fromisoformat(row["expires_at"])
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > exp:
                    return None
            conn.execute(
                "UPDATE api_tokens SET last_used_at = ? WHERE id = ?",
                (_now(), row["token_id"]),
            )
            conn.commit()
        return {
            "user_id": row["user_id"],
            "username": row["username"],
            "role": row["role"],
            "token_id": row["token_id"],
        }
    except Exception:
        return None


def list_api_tokens(user_id: str) -> list[dict]:
    """List all tokens for a user (never returns the hash or plain token)."""
    _ensure_db()
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT id, name, token_prefix, created_at, last_used_at, expires_at, enabled
               FROM api_tokens
               WHERE user_id = ?
               ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_api_token(token_id: str, user_id: str) -> bool:
    """Permanently delete a token. Only the owner can delete their own tokens."""
    with _get_conn() as conn:
        cursor = conn.execute(
            "DELETE FROM api_tokens WHERE id = ? AND user_id = ?",
            (token_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def admin_delete_api_token(token_id: str) -> bool:
    """Admin-level delete — can remove any token regardless of owner."""
    with _get_conn() as conn:
        cursor = conn.execute("DELETE FROM api_tokens WHERE id = ?", (token_id,))
        conn.commit()
        return cursor.rowcount > 0


def list_all_api_tokens() -> list[dict]:
    """Admin view — list all tokens with username."""
    _ensure_db()
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT t.id, t.name, t.token_prefix, t.created_at, t.last_used_at,
                      t.expires_at, t.enabled, u.username
               FROM api_tokens t
               JOIN users u ON t.user_id = u.id
               ORDER BY t.created_at DESC""",
        ).fetchall()
        return [dict(r) for r in rows]


# ===== App Settings (key-value store for application-wide flags) =====

def get_app_setting(key: str, default: str | None = None) -> str | None:
    """Read a single application setting by key. Returns default if not set."""
    try:
        _ensure_db()
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else default
    except Exception:
        return default


def set_app_setting(key: str, value: str) -> None:
    """Write (upsert) an application setting."""
    _ensure_db()
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, _now()),
        )
        conn.commit()


# Convenience wrappers for the setup wizard flag
def is_setup_complete() -> bool:
    return get_app_setting("setup_wizard_complete", "0") == "1"


def mark_setup_complete() -> None:
    set_app_setting("setup_wizard_complete", "1")
