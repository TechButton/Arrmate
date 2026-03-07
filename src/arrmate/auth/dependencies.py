"""FastAPI dependencies for route protection."""

from urllib.parse import urlparse

from fastapi import Header, HTTPException, Request

from . import auth_manager
from .session import SESSION_COOKIE, validate_session_token


class AuthRedirectException(Exception):
    """Raised when an unauthenticated web request needs to redirect to login."""

    def __init__(self, login_url: str, is_htmx: bool = False):
        self.login_url = login_url
        self.is_htmx = is_htmx


_HTMX_PARTIAL_PATHS = {
    "/web/notifications",
    "/web/notifications/count",
}


def safe_next_url(url: str | None) -> str:
    """Validate that redirect URL is safe (internal web path only).

    HTMX partial paths that return HTML fragments are excluded because
    navigating to them directly (e.g. after a post-login redirect) would
    render a bare fragment — appearing blank to the user.
    """
    if not url:
        return "/web/"
    parsed = urlparse(url)
    if parsed.scheme or parsed.netloc:
        return "/web/"
    if not url.startswith("/web/"):
        return "/web/"
    # Strip query string before checking partial paths
    path_only = parsed.path
    if path_only in _HTMX_PARTIAL_PATHS:
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


async def get_api_user(authorization: str | None = Header(default=None)) -> dict:
    """API dependency — validate Bearer token and return the authenticated user dict.

    Usage::

        @app.get("/api/v1/something")
        async def handler(user: dict = Depends(get_api_user)):
            ...

    The returned dict contains: user_id, username, role, token_id.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Bearer token required. Create a token at /web/api-tokens.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[7:].strip()
    from .user_db import validate_api_token
    user = validate_api_token(token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid, expired, or revoked API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
