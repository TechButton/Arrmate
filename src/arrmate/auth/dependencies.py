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


def get_current_user(request: Request) -> dict | None:
    """Get the current user from session cookie. Returns user dict or None."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return validate_session_token(token, auth_manager.get_secret_key())


async def require_any_auth(request: Request) -> None:
    """Web route dependency — always require authentication."""
    user = get_current_user(request)
    if user:
        # Enforce must_change_password: block access to all protected routes until changed
        uid = user.get("user_id") or user.get("id", "")
        if uid and uid != "legacy":
            try:
                from .user_db import get_user_by_id
                db_user = get_user_by_id(uid)
                if db_user and db_user.get("must_change_password"):
                    if request.url.path != "/web/change-password":
                        is_htmx = bool(request.headers.get("HX-Request"))
                        raise AuthRedirectException("/web/change-password", is_htmx=is_htmx)
            except AuthRedirectException:
                raise
            except Exception:
                pass
        return

    next_url = str(request.url.path)
    if request.url.query:
        next_url += f"?{request.url.query}"

    login_url = f"/web/login?next={next_url}"
    is_htmx = bool(request.headers.get("HX-Request"))
    raise AuthRedirectException(login_url, is_htmx=is_htmx)


# Backwards-compat alias
async def require_auth(request: Request) -> None:
    """Backwards-compat alias for require_any_auth."""
    return await require_any_auth(request)


async def require_admin(request: Request) -> None:
    """Redirect to login if not authenticated; 403 if not admin."""
    user = get_current_user(request)
    if not user:
        next_url = str(request.url.path)
        login_url = f"/web/login?next={next_url}"
        is_htmx = bool(request.headers.get("HX-Request"))
        raise AuthRedirectException(login_url, is_htmx=is_htmx)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


async def require_power_user(request: Request) -> None:
    """Redirect to login if not authenticated; 403 if not admin or power_user."""
    user = get_current_user(request)
    if not user:
        next_url = str(request.url.path)
        login_url = f"/web/login?next={next_url}"
        is_htmx = bool(request.headers.get("HX-Request"))
        raise AuthRedirectException(login_url, is_htmx=is_htmx)
    if user.get("role") not in ("admin", "power_user"):
        raise HTTPException(status_code=403, detail="Power user or admin access required")


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
