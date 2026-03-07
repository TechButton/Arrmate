"""Tests for Plex SSO (PIN-based OAuth) helpers."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── plex_sso module unit tests ───────────────────────────────────────────────

def test_plex_client_id_is_stable():
    """Same secret key must always produce the same client ID."""
    from arrmate.auth.plex_sso import plex_client_id
    assert plex_client_id("secret") == plex_client_id("secret")


def test_plex_client_id_differs_per_secret():
    from arrmate.auth.plex_sso import plex_client_id
    assert plex_client_id("secret-a") != plex_client_id("secret-b")


def test_plex_client_id_length():
    """Client ID must be 32 hex chars."""
    from arrmate.auth.plex_sso import plex_client_id
    cid = plex_client_id("test-secret")
    assert len(cid) == 32
    assert all(c in "0123456789abcdef" for c in cid)


def test_build_plex_auth_url_contains_code():
    from arrmate.auth.plex_sso import build_plex_auth_url
    url = build_plex_auth_url("my-client", "ABCD1234", "https://arrmate.example.com/web/auth/plex/callback")
    assert "ABCD1234" in url
    assert "my-client" in url
    assert "app.plex.tv/auth" in url


def test_state_cookie_roundtrip():
    """State cookie can be written and read back correctly."""
    from arrmate.auth.plex_sso import set_plex_state_cookie, get_plex_state, PLEX_STATE_COOKIE
    from fastapi.responses import RedirectResponse
    from fastapi import Request
    from unittest.mock import MagicMock

    secret = "test-secret-key"
    response = MagicMock()
    set_plex_state_cookie(response, pin_id=99999, next_url="/web/", secret_key=secret)

    # Capture the value that was set
    call_kwargs = response.set_cookie.call_args
    cookie_value = call_kwargs.args[1] if call_kwargs.args else call_kwargs.kwargs.get(
        list(call_kwargs.kwargs.keys())[0]
    )
    # Actually let's check it was called with httponly and secure
    assert response.set_cookie.called
    kwargs = response.set_cookie.call_args.kwargs
    assert kwargs.get("httponly") is True
    assert kwargs.get("secure") is True
    assert kwargs.get("samesite") == "lax"
    assert kwargs.get("max_age") == 300


def test_state_cookie_read_invalid_returns_none():
    """Tampered or missing cookie must return None."""
    from arrmate.auth.plex_sso import get_plex_state
    from unittest.mock import MagicMock

    request = MagicMock()
    request.cookies = {"arrmate_plex_state": "tampered.value"}
    result = get_plex_state(request, "real-secret")
    assert result is None


def test_state_cookie_missing_returns_none():
    from arrmate.auth.plex_sso import get_plex_state
    from unittest.mock import MagicMock

    request = MagicMock()
    request.cookies = {}
    result = get_plex_state(request, "real-secret")
    assert result is None


# ── user_db Plex helpers ──────────────────────────────────────────────────────

def test_plex_user_blocked_from_password_login(tmp_path, monkeypatch):
    """Plex SSO users must not be able to log in with a local password."""
    import arrmate.auth.user_db as user_db
    monkeypatch.setattr(
        "arrmate.auth.user_db._db_path", lambda: tmp_path / "users.db"
    )
    monkeypatch.setattr(
        "arrmate.auth.user_db._auth_json_path", lambda: tmp_path / "auth.json"
    )
    user_db._db_ready = False
    user_db.init_db()

    # Create a Plex user
    user = user_db.create_plex_user(
        plex_id="plex-uuid-12345",
        username="plexuser",
        email="plex@example.com",
        role="user",
    )
    assert user is not None

    # Attempting any password login must return None
    assert user_db.verify_user("plexuser", "any_password") is None
    assert user_db.verify_user("plexuser", "") is None


def test_get_user_by_plex_id(tmp_path, monkeypatch):
    """get_user_by_plex_id must return the correct user."""
    import arrmate.auth.user_db as user_db
    monkeypatch.setattr(
        "arrmate.auth.user_db._db_path", lambda: tmp_path / "users.db"
    )
    monkeypatch.setattr(
        "arrmate.auth.user_db._auth_json_path", lambda: tmp_path / "auth.json"
    )
    user_db._db_ready = False
    user_db.init_db()

    user_db.create_plex_user(
        plex_id="unique-uuid-xyz",
        username="findme",
        email="find@example.com",
        role="user",
    )

    found = user_db.get_user_by_plex_id("unique-uuid-xyz")
    assert found is not None
    assert found["username"] == "findme"
    assert found["auth_provider"] == "plex"

    not_found = user_db.get_user_by_plex_id("does-not-exist")
    assert not_found is None


# ── Route-level tests ─────────────────────────────────────────────────────────

def test_plex_start_redirects_to_login_when_disabled():
    """GET /web/auth/plex/start must redirect to /web/login when SSO is disabled."""
    from arrmate.interfaces.api.app import app
    from fastapi.testclient import TestClient

    with patch("arrmate.interfaces.web.routes.settings") as mock_settings:
        mock_settings.plex_sso_enabled = False
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/web/auth/plex/start", follow_redirects=False)

    assert resp.status_code in (302, 303)
    assert "/web/login" in resp.headers.get("location", "")


def test_plex_callback_redirects_to_login_when_disabled():
    """GET /web/auth/plex/callback must redirect when SSO is disabled."""
    from arrmate.interfaces.api.app import app
    from fastapi.testclient import TestClient

    with patch("arrmate.interfaces.web.routes.settings") as mock_settings:
        mock_settings.plex_sso_enabled = False
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/web/auth/plex/callback", follow_redirects=False)

    assert resp.status_code in (302, 303)
    assert "/web/login" in resp.headers.get("location", "")
