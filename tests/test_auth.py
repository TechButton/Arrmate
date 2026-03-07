"""Tests for authentication session management and user database."""
import logging
from unittest.mock import MagicMock

from arrmate.auth.session import SESSION_COOKIE, set_session_cookie


# ── Session cookie flags ───────────────────────────────────────────────────────


def test_session_cookie_has_secure_flag():
    """Session cookie must set secure=True to prevent transmission over HTTP."""
    response = MagicMock()
    set_session_cookie(response, "test-token")
    call_kwargs = response.set_cookie.call_args.kwargs
    assert call_kwargs.get("secure") is True, "Cookie must have secure=True"


def test_session_cookie_has_httponly_flag():
    """Session cookie must be httponly to prevent JS access."""
    response = MagicMock()
    set_session_cookie(response, "test-token")
    assert response.set_cookie.call_args.kwargs.get("httponly") is True


def test_session_cookie_has_samesite_lax():
    """Session cookie must use samesite=lax."""
    response = MagicMock()
    set_session_cookie(response, "test-token")
    assert response.set_cookie.call_args.kwargs.get("samesite") == "lax"


# ── Default admin credentials ─────────────────────────────────────────────────


def test_default_admin_creation_does_not_log_password(tmp_path, caplog, monkeypatch):
    """Default admin creation must not log the plain-text default password."""
    from arrmate.auth import user_db as _user_db

    monkeypatch.setattr(_user_db, "_db_path", lambda: tmp_path / "users.db")

    with caplog.at_level(logging.DEBUG, logger="arrmate.auth.user_db"):
        _user_db._create_default_admin()

    full_log = " ".join(caplog.messages)
    assert "changeme123" not in full_log, "Plain-text default password must not appear in logs"


# ── Minimum password length ───────────────────────────────────────────────────


def test_minimum_password_length_is_at_least_eight():
    """Password minimum must be >= 8 characters (NIST SP 800-63B)."""
    import inspect
    from arrmate.interfaces.web import routes as _routes

    source = inspect.getsource(_routes)
    assert "len(password) < 4" not in source, \
        "Found 4-character minimum — must be at least 8"
    assert any(f"len(password) < {n}" in source for n in range(8, 20)), \
        "Expected minimum password length >= 8 not found in routes source"
