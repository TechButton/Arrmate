"""Authentication manager — credential storage and verification."""

import json
import logging
import os
import secrets
import tempfile
from pathlib import Path

from passlib.hash import bcrypt

from ..config.settings import settings

logger = logging.getLogger(__name__)


class AuthManager:
    """Manages user credentials stored in a JSON file."""

    def __init__(self) -> None:
        self._data_dir = Path(settings.auth_data_dir)
        self._auth_file = self._data_dir / "auth.json"
        self._generated_secret: str | None = None

    def _read(self) -> dict:
        """Read auth data from file."""
        if not self._auth_file.exists():
            return {}
        try:
            return json.loads(self._auth_file.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to read auth file, treating as empty")
            return {}

    def _write(self, data: dict) -> None:
        """Atomically write auth data to file."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=str(self._data_dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, str(self._auth_file))
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def has_credentials(self) -> bool:
        """Check if any credentials are stored."""
        data = self._read()
        return bool(data.get("username"))

    def is_auth_required(self) -> bool:
        """Check if authentication is currently required."""
        data = self._read()
        return bool(data.get("username") and data.get("enabled", False))

    def set_credentials(self, username: str, password: str) -> None:
        """Create or replace credentials. Automatically enables auth."""
        data = self._read()
        data["username"] = username
        data["password_hash"] = bcrypt.hash(password)
        data["enabled"] = True
        self._write(data)
        logger.info("Auth credentials set for user: %s", username)

    def verify(self, username: str, password: str) -> bool:
        """Verify username and password against stored credentials."""
        data = self._read()
        stored_user = data.get("username")
        stored_hash = data.get("password_hash")
        if not stored_user or not stored_hash:
            return False
        if username != stored_user:
            return False
        return bcrypt.verify(password, stored_hash)

    def enable(self) -> None:
        """Enable authentication (credentials must exist)."""
        data = self._read()
        if not data.get("username"):
            raise ValueError("No credentials to enable")
        data["enabled"] = True
        self._write(data)
        logger.info("Auth enabled")

    def disable(self) -> None:
        """Disable authentication without deleting credentials."""
        data = self._read()
        data["enabled"] = False
        self._write(data)
        logger.info("Auth disabled")

    def delete(self) -> None:
        """Delete all credentials."""
        if self._auth_file.exists():
            self._auth_file.unlink()
        logger.info("Auth credentials deleted")

    def get_username(self) -> str | None:
        """Get the stored username, if any."""
        data = self._read()
        return data.get("username")

    def is_enabled(self) -> bool:
        """Check if auth is enabled (may be disabled even with credentials)."""
        data = self._read()
        return data.get("enabled", False)

    def get_secret_key(self) -> str:
        """Get secret key for session signing. Auto-generates if not configured."""
        if settings.secret_key:
            return settings.secret_key
        if self._generated_secret is None:
            self._generated_secret = secrets.token_hex(32)
            logger.info("Auto-generated session secret key")
        return self._generated_secret
