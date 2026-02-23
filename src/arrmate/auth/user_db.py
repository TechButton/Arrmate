"""SQLite user database for multi-user authentication."""

import json
import logging
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator

from passlib.hash import bcrypt

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
        """)
        conn.commit()

        # Migration: add must_change_password column if it doesn't exist yet
        try:
            conn.execute(
                "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0"
            )
            conn.commit()
        except Exception:
            pass  # Column already exists

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
        password_hash = bcrypt.hash("changeme123")
        with _get_conn() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO users
                   (id, username, password_hash, role, enabled, created_at, must_change_password)
                   VALUES (?, 'admin', ?, 'admin', 1, ?, 1)""",
                (_new_id(), password_hash, _now()),
            )
            conn.commit()
        logger.info("Created default admin account (username: admin, password: changeme123)")
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
    password_hash = bcrypt.hash(password)
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
    """Verify credentials. Returns user dict or None if invalid/disabled."""
    user = get_user_by_username(username)
    if not user or not user.get("enabled"):
        return None
    try:
        if bcrypt.verify(password, user["password_hash"]):
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
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [user_id]
    with _get_conn() as conn:
        cursor = conn.execute(
            f"UPDATE users SET {set_clause} WHERE id = ?", values
        )
        conn.commit()
        return cursor.rowcount > 0


def change_password(user_id: str, new_password: str) -> bool:
    """Change a user's password and clear must_change_password flag. Returns True on success."""
    password_hash = bcrypt.hash(new_password)
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
