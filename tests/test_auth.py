"""Tests for authentication session management and user database."""
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
