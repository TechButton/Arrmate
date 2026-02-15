"""FastAPI dependencies for route protection."""

import base64
import binascii
from urllib.parse import urlparse

from fastapi import HTTPException, Request

from . import auth_manager
from .session import SESSION_COOKIE, validate_session_token


class AuthRedirectException(Exception):
    """Raised when an unauthenticated web request needs to redirect to login."""

    def __init__(self, login_url: str, is_htmx: bool = False):
        self.login_url = login_url
        self.is_htmx = is_htmx


def safe_next_url(url: str | None) -> str:
    """Validate that redirect URL is safe (internal web path only)."""
    if not url:
        return "/web/"
    parsed = urlparse(url)
    if parsed.scheme or parsed.netloc:
        return "/web/"
    if not url.startswith("/web/"):
        return "/web/"
    return url


async def require_auth(request: Request) -> None:
    """Web route dependency — redirect to login if auth is required and not authenticated."""
    if not auth_manager.is_auth_required():
        return

    token = request.cookies.get(SESSION_COOKIE)
    if token:
        username = validate_session_token(token, auth_manager.get_secret_key())
        if username:
            return

    next_url = str(request.url.path)
    if request.url.query:
        next_url += f"?{request.url.query}"

    login_url = f"/web/login?next={next_url}"
    is_htmx = bool(request.headers.get("HX-Request"))

    raise AuthRedirectException(login_url, is_htmx=is_htmx)


async def require_api_auth(request: Request) -> None:
    """API route dependency — HTTP Basic Auth when auth is required."""
    if not auth_manager.is_auth_required():
        return

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            username, password = decoded.split(":", 1)
            if auth_manager.verify(username, password):
                return
        except (binascii.Error, ValueError, UnicodeDecodeError):
            pass

    raise HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": 'Basic realm="Arrmate API"'},
    )
