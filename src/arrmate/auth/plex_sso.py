"""Plex SSO (PIN-based OAuth) helpers for Arrmate.

Flow:
  1. GET /web/auth/plex/start
       → POST plex.tv/api/v2/pins (get pin_id + code)
       → store {pin_id, next} in a short-lived signed state cookie
       → redirect browser to app.plex.tv/auth with the code

  2. GET /web/auth/plex/callback
       → read + validate state cookie (CSRF protection)
       → GET plex.tv/api/v2/pins/{pin_id} → authToken
       → GET plex.tv/api/v2/user with authToken → plex user info
       → look up / create local DB user
       → issue arrmate session cookie, clear state cookie, redirect

Security notes:
- The Plex authToken is NEVER stored; it is used once to fetch user identity then discarded.
- The state cookie is signed (itsdangerous), httponly, secure, samesite=lax, max-age=5 min.
- Pin IDs are integers from Plex's API; they are type-validated before use.
"""

import hashlib
from typing import Optional, Tuple

import httpx
from fastapi import Request
from fastapi.responses import Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .session import _COOKIE_SECURE


PLEX_TV_API = "https://plex.tv/api/v2"
PLEX_APP_AUTH = "https://app.plex.tv/auth"

# Short-lived state cookie that carries the pin_id across the redirect round-trip.
PLEX_STATE_COOKIE = "arrmate_plex_state"
PLEX_STATE_MAX_AGE = 300  # 5 minutes — more than enough for a human to authorise

_PLEX_HEADERS = {
    "X-Plex-Product": "Arrmate",
    "X-Plex-Version": "1.0",
    "Accept": "application/json",
}


# ── Client identifier ────────────────────────────────────────────────────────

def plex_client_id(secret_key: str) -> str:
    """Derive a stable, instance-specific Plex Client Identifier.

    Plex requires the same clientID on every request from an integration.
    We derive it deterministically from the instance secret so it is stable
    across restarts without needing a separate setting.
    """
    return hashlib.sha256(
        f"arrmate-plex-client-{secret_key}".encode()
    ).hexdigest()[:32]


# ── Plex API calls ───────────────────────────────────────────────────────────

async def request_pin(client_id: str) -> Tuple[int, str]:
    """Request a new PIN from plex.tv.

    Returns (pin_id: int, pin_code: str).
    Raises httpx.HTTPStatusError on API failure.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{PLEX_TV_API}/pins",
            headers={**_PLEX_HEADERS, "X-Plex-Client-Identifier": client_id},
            json={"strong": True},
        )
        resp.raise_for_status()
        data = resp.json()
        return int(data["id"]), str(data["code"])


async def validate_pin(pin_id: int, client_id: str) -> Optional[str]:
    """Check whether a PIN has been claimed by the user.

    Returns the authToken string if the user has authorised, or None if not
    yet authorised or if the pin has expired.
    Raises httpx.HTTPStatusError on network / API error.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{PLEX_TV_API}/pins/{pin_id}",
            headers={**_PLEX_HEADERS, "X-Plex-Client-Identifier": client_id},
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("authToken")
        return str(token) if token else None


async def get_plex_user(auth_token: str) -> dict:
    """Fetch the Plex user profile for the given authToken.

    The returned dict always contains at least: uuid (str), username (str).
    Raises httpx.HTTPStatusError on failure.

    IMPORTANT: The caller must not persist auth_token after this call.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{PLEX_TV_API}/user",
            headers={
                **_PLEX_HEADERS,
                "X-Plex-Token": auth_token,
            },
        )
        resp.raise_for_status()
        return resp.json()


# ── Auth URL builder ─────────────────────────────────────────────────────────

def build_plex_auth_url(client_id: str, code: str, forward_url: str) -> str:
    """Build the plex.tv auth page URL.

    The browser is redirected here so the user can log in and authorise
    Arrmate.  Plex will redirect them back to forward_url when done.
    """
    from urllib.parse import urlencode
    params = urlencode({
        "clientID": client_id,
        "code": code,
        "forwardUrl": forward_url,
        "context[device][product]": "Arrmate",
    })
    # Plex auth uses a fragment (hash) URL, not a query string
    return f"{PLEX_APP_AUTH}#{params}"


# ── State cookie ─────────────────────────────────────────────────────────────

def set_plex_state_cookie(
    response: Response,
    pin_id: int,
    next_url: str,
    secret_key: str,
) -> None:
    """Embed {pin_id, next_url} into a short-lived signed cookie.

    Using a separate salt ("plex-sso-state") keeps this token namespace
    isolated from session tokens signed with the same secret key.
    """
    s = URLSafeTimedSerializer(secret_key, salt="plex-sso-state")
    value = s.dumps({"pin_id": pin_id, "next": next_url})
    response.set_cookie(
        PLEX_STATE_COOKIE,
        value,
        max_age=PLEX_STATE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=_COOKIE_SECURE,
    )


def get_plex_state(
    request: Request,
    secret_key: str,
) -> Optional[Tuple[int, str]]:
    """Read and validate the Plex state cookie.

    Returns (pin_id, next_url) on success, or None if the cookie is missing,
    tampered with, or expired.
    """
    token = request.cookies.get(PLEX_STATE_COOKIE)
    if not token:
        return None
    s = URLSafeTimedSerializer(secret_key, salt="plex-sso-state")
    try:
        data = s.loads(token, max_age=PLEX_STATE_MAX_AGE)
        return int(data["pin_id"]), str(data["next"])
    except (BadSignature, SignatureExpired, KeyError, ValueError, TypeError):
        return None


def clear_plex_state_cookie(response: Response) -> None:
    """Delete the Plex state cookie from the response."""
    response.delete_cookie(PLEX_STATE_COOKIE, samesite="lax")
