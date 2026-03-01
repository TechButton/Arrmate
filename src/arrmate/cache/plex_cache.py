"""SQLite cache for Plex watch history.

Stores a local copy of Plex watch history so the By Title view loads instantly
instead of fetching from the Plex API on every page load.
Cache is refreshed on demand (manual sync) or when first loading after startup.
"""

import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

# Time-to-live in seconds before the cache is considered stale
CACHE_TTL = 15 * 60  # 15 minutes


def _db_path() -> Path:
    from ..config.settings import settings

    return Path(settings.auth_data_dir) / "plex_cache.db"


@contextmanager
def _get_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        conn.close()


def init_cache() -> None:
    """Create tables if they don't exist."""
    _db_path().parent.mkdir(parents=True, exist_ok=True)
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS plex_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rating_key TEXT,
                title TEXT NOT NULL,
                grandparent_title TEXT,
                type TEXT NOT NULL,
                thumb TEXT,
                grandparent_thumb TEXT,
                viewed_at INTEGER NOT NULL,
                account_id INTEGER,
                synced_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS plex_cache_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        conn.commit()


def _ensure_init() -> None:
    try:
        init_cache()
    except Exception as e:
        logger.warning("Could not init Plex cache: %s", e)


def get_last_synced() -> Optional[int]:
    """Return Unix timestamp of last successful sync, or None."""
    try:
        _ensure_init()
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM plex_cache_meta WHERE key='last_synced'"
            ).fetchone()
            return int(row["value"]) if row else None
    except Exception:
        return None


def is_stale() -> bool:
    """Return True if cache is empty or older than CACHE_TTL."""
    last = get_last_synced()
    if last is None:
        return True
    return (time.time() - last) > CACHE_TTL


def get_cache_size() -> int:
    """Return number of rows in the history cache."""
    try:
        _ensure_init()
        with _get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM plex_history").fetchone()[0]
    except Exception:
        return 0


def populate_cache(items: List[Dict[str, Any]]) -> int:
    """Replace cache with a fresh list of Plex history items.

    Args:
        items: Raw Plex history Metadata items from the API.

    Returns:
        Number of rows stored.
    """
    now = int(time.time())
    try:
        _ensure_init()
        with _get_conn() as conn:
            conn.execute("DELETE FROM plex_history")
            conn.executemany(
                """INSERT INTO plex_history
                   (rating_key, title, grandparent_title, type, thumb, grandparent_thumb,
                    viewed_at, account_id, synced_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        item.get("ratingKey"),
                        item.get("title") or "",
                        item.get("grandparentTitle"),
                        item.get("type") or "",
                        item.get("thumb"),
                        item.get("grandparentThumb"),
                        item.get("viewedAt") or 0,
                        item.get("accountID"),
                        now,
                    )
                    for item in items
                ],
            )
            conn.execute(
                "INSERT OR REPLACE INTO plex_cache_meta (key, value) VALUES ('last_synced', ?)",
                (str(now),),
            )
            conn.commit()
            return len(items)
    except Exception as e:
        logger.error("Failed to populate Plex cache: %s", e)
        return 0


def get_cached_history() -> List[Dict[str, Any]]:
    """Return all cached history rows as plain dicts."""
    try:
        _ensure_init()
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM plex_history ORDER BY viewed_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.warning("Failed to read Plex cache: %s", e)
        return []
