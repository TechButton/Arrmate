"""Tests for the in-memory rate limiter."""
import asyncio
import pytest


@pytest.mark.asyncio
async def test_allows_calls_within_limit():
    from arrmate.auth.rate_limit import RateLimiter
    limiter = RateLimiter(max_calls=3, window_seconds=60)
    for _ in range(3):
        allowed, retry_after = await limiter.check("127.0.0.1")
        assert allowed
        assert retry_after == 0


@pytest.mark.asyncio
async def test_blocks_call_exceeding_limit():
    from arrmate.auth.rate_limit import RateLimiter
    limiter = RateLimiter(max_calls=3, window_seconds=60)
    for _ in range(3):
        await limiter.check("127.0.0.1")
    allowed, retry_after = await limiter.check("127.0.0.1")
    assert not allowed
    assert retry_after > 0


@pytest.mark.asyncio
async def test_different_ips_are_independent():
    from arrmate.auth.rate_limit import RateLimiter
    limiter = RateLimiter(max_calls=1, window_seconds=60)
    allowed_a, _ = await limiter.check("1.1.1.1")
    assert allowed_a
    # Exhaust 1.1.1.1
    await limiter.check("1.1.1.1")
    # 2.2.2.2 should still be fine
    allowed_b, _ = await limiter.check("2.2.2.2")
    assert allowed_b


@pytest.mark.asyncio
async def test_window_resets_after_expiry():
    """After the window expires the counter resets and calls are allowed again."""
    from arrmate.auth.rate_limit import RateLimiter
    import time

    limiter = RateLimiter(max_calls=1, window_seconds=1)
    await limiter.check("10.0.0.1")  # use up the quota
    blocked, _ = await limiter.check("10.0.0.1")
    assert not blocked

    # Manually wind back the window start to simulate expiry
    limiter._counters["10.0.0.1"][1] = time.monotonic() - 2

    allowed, _ = await limiter.check("10.0.0.1")
    assert allowed


def test_login_endpoint_returns_429_after_limit(client):
    """POST /web/login returns 429 after rate limit is exhausted."""
    from arrmate.auth.rate_limit import login_limiter, RateLimiter
    import unittest.mock as mock

    # Patch the shared limiter to always deny
    with mock.patch.object(
        login_limiter, "check", new=mock.AsyncMock(return_value=(False, 30))
    ):
        resp = client.post(
            "/web/login",
            data={"username": "admin", "password": "wrong", "next": "/web/"},
        )

    assert resp.status_code == 429


def test_api_token_endpoint_returns_429_after_limit():
    """POST /api/v1/auth/token returns 429 when rate limited."""
    from arrmate.interfaces.api.app import app
    from arrmate.auth.rate_limit import login_limiter
    from fastapi.testclient import TestClient
    import unittest.mock as mock

    test_client = TestClient(app, raise_server_exceptions=False)
    with mock.patch.object(
        login_limiter, "check", new=mock.AsyncMock(return_value=(False, 30))
    ):
        resp = test_client.post(
            "/api/v1/auth/token",
            json={"username": "admin", "password": "wrong"},
        )

    assert resp.status_code == 429
