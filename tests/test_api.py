"""Tests for the FastAPI application."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock


@pytest.fixture
def client():
    from arrmate.interfaces.api.app import app
    return TestClient(app, raise_server_exceptions=False)


def test_execute_command_rejects_oversized_input(client):
    """Commands over 2000 characters must be rejected with 422."""
    oversized = "a" * 2001
    resp = client.post(
        "/api/v1/execute",
        json={"command": oversized},
        headers={"Authorization": "Bearer fake-token"},
    )
    assert resp.status_code == 422, f"Expected 422 for oversized input, got {resp.status_code}"


def test_execute_command_accepts_max_length_input(client):
    """Commands of exactly 2000 characters must not be rejected by length validation."""
    exactly_max = "a" * 2000
    resp = client.post(
        "/api/v1/execute",
        json={"command": exactly_max},
        headers={"Authorization": "Bearer fake-token"},
    )
    # 401 because fake token is fine — what we care about is NOT getting 422 for length
    assert resp.status_code != 422, "2000-char command should not fail length validation"


def test_500_response_body_is_generic():
    """Internal exceptions must return a generic message, not internal detail."""
    from arrmate.interfaces.api.app import app
    from arrmate.auth.dependencies import get_api_user

    # Override auth to get past the bearer check
    app.dependency_overrides[get_api_user] = lambda: {
        "user_id": "test", "username": "test", "role": "admin", "token_id": "test"
    }
    test_client = TestClient(app, raise_server_exceptions=False)

    with patch("arrmate.interfaces.api.app.parser") as mock_parser:
        mock_parser.parse = AsyncMock(
            side_effect=RuntimeError("internal path /data/users.db exposed")
        )
        resp = test_client.post("/api/v1/execute", json={"command": "list shows"})

    app.dependency_overrides.clear()

    assert resp.status_code == 500
    assert "/data/users.db" not in resp.text
    assert "internal path" not in resp.text
    assert "internal error" in resp.text.lower()
