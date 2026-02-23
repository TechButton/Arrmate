"""Web routes for Arrmate HTMX interface."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ...auth import auth_manager
from ...auth import user_db
from ...auth.dependencies import (
    get_current_user,
    require_any_auth,
    require_auth,
    require_admin,
    require_power_user,
    safe_next_url,
)
from ...auth.notifications import notify_request_resolved, notify_request_submitted
from ...auth.session import (
    clear_session_cookie,
    create_session_token,
    set_session_cookie,
)
from ...clients.discovery import discover_services, get_client_for_media_type
from ...config.service_config import save_service_config
from ...clients.plex import PlexClient
from ...clients.plex_tv import PlexTVClient
from ...clients.radarr import RadarrClient
from ...clients.sonarr import SonarrClient
from ...clients.transcoder import cancel_job, get_all_jobs, get_job
from ...config.settings import settings
from ...core.command_parser import CommandParser
from ...core.executor import Executor
from ...core.intent_engine import IntentEngine
from ...core.models import ActionType

logger = logging.getLogger(__name__)

# Protected router — all routes require auth when enabled
router = APIRouter(prefix="/web", tags=["web"], dependencies=[Depends(require_auth)])

# Auth router — login/logout/register routes (no auth dependency)
auth_router = APIRouter(prefix="/web", tags=["auth"])

# Get templates directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Make auth_manager and settings available in all templates
templates.env.globals["auth_manager"] = auth_manager
templates.env.globals["settings"] = settings


def _timestamp_to_relative(ts: int) -> str:
    """Convert a Unix timestamp to a human-readable relative string."""
    import time
    delta = int(time.time()) - ts
    if delta < 60:
        return "just now"
    if delta < 3600:
        m = delta // 60
        return f"{m}m ago"
    if delta < 86400:
        h = delta // 3600
        return f"{h}h ago"
    if delta < 604800:
        d = delta // 86400
        return f"{d}d ago"
    if delta < 2592000:
        w = delta // 604800
        return f"{w}w ago"
    mo = delta // 2592000
    return f"{mo}mo ago"


templates.env.filters["timestamp_to_relative"] = _timestamp_to_relative

# Global components (shared with API)
parser: Optional[CommandParser] = None
engine: Optional[IntentEngine] = None
executor: Optional[Executor] = None

# Destructive actions blocked for 'user' role
_USER_BLOCKED_ACTIONS = {ActionType.REMOVE, ActionType.DELETE}


async def get_parser() -> CommandParser:
    """Get or create command parser, with service-aware prompt on first init."""
    global parser
    if parser is None:
        services = await discover_services()
        available = [name for name, info in services.items() if info.available]
        parser = CommandParser(available_services=available or None)
    return parser


def get_engine() -> IntentEngine:
    """Get or create intent engine."""
    global engine
    if engine is None:
        engine = IntentEngine()
    return engine


def get_executor() -> Executor:
    """Get or create executor."""
    global executor
    if executor is None:
        executor = Executor()
    return executor


def reset_parser() -> None:
    """Reset the cached parser so the next command re-initialises it with current services."""
    global parser
    parser = None


def _base_ctx(request: Request) -> dict:
    """Base template context: current user + unread notification count."""
    user = get_current_user(request)
    unread = 0
    if user:
        uid = user.get("user_id") or user.get("id", "")
        if uid and uid != "legacy":
            try:
                unread = user_db.get_unread_count(uid)
            except Exception:
                pass
            # Merge must_change_password from DB into session dict
            try:
                db_user = user_db.get_user_by_id(uid)
                if db_user:
                    user = {**user, "must_change_password": db_user.get("must_change_password", 0)}
            except Exception:
                pass
    return {"current_user": user, "unread_count": unread}


# ===== Auth Routes (unprotected) =====


@auth_router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    next: str = Query(default="/web/"),
    error: str = Query(default=""),
):
    """Login page. Redirects to register only if truly no users exist."""
    try:
        no_users = not user_db.has_any_users()
    except Exception:
        no_users = False  # If DB check fails, show login page rather than risk a redirect loop

    if no_users:
        return RedirectResponse(url="/web/register", status_code=303)

    return templates.TemplateResponse(
        "pages/login.html",
        {
            "request": request,
            "next": safe_next_url(next),
            "error": error,
        },
    )


@auth_router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form(default="/web/"),
):
    """Process login form submission."""
    # Try new multi-user DB first
    user = None
    try:
        user = user_db.verify_user(username, password)
    except Exception:
        pass

    # Fall back to legacy single-user auth
    if user is None and auth_manager.verify(username, password):
        legacy_username = auth_manager.get_username() or username
        user = {"user_id": "legacy", "username": legacy_username, "role": "admin"}

    if user:
        uid = user.get("user_id") or user.get("id", "")
        token = create_session_token(
            uid,
            user["username"],
            user["role"],
            auth_manager.get_secret_key(),
        )
        # Redirect to change-password if required (e.g. default admin account)
        if user.get("must_change_password"):
            response = RedirectResponse(url="/web/change-password", status_code=303)
        else:
            redirect_url = safe_next_url(next)
            response = RedirectResponse(url=redirect_url, status_code=303)
        set_session_cookie(response, token)
        return response

    return templates.TemplateResponse(
        "pages/login.html",
        {
            "request": request,
            "next": safe_next_url(next),
            "error": "Invalid username or password",
        },
        status_code=401,
    )


@auth_router.get("/logout")
async def logout():
    """Log out and redirect to login."""
    response = RedirectResponse(url="/web/login", status_code=303)
    clear_session_cookie(response)
    return response


@auth_router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request):
    """Show the change-password form."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/web/login", status_code=303)
    return templates.TemplateResponse(
        "pages/change_password.html",
        {"request": request, "error": None, **_base_ctx(request)},
    )


@auth_router.post("/change-password", response_class=HTMLResponse)
async def change_password_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    """Process the change-password form."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/web/login", status_code=303)

    def _error(msg: str):
        return templates.TemplateResponse(
            "pages/change_password.html",
            {"request": request, "error": msg, **_base_ctx(request)},
            status_code=422,
        )

    if len(new_password) < 4:
        return _error("New password must be at least 4 characters.")
    if new_password != confirm_password:
        return _error("Passwords do not match.")

    uid = user.get("user_id") or user.get("id", "")
    # Verify current password against DB (legacy users can skip)
    if uid and uid != "legacy":
        db_user = user_db.get_user_by_id(uid)
        if db_user:
            verified = user_db.verify_user(db_user["username"], current_password)
            if not verified:
                return _error("Current password is incorrect.")
            user_db.change_password(uid, new_password)
        else:
            return _error("User not found.")
    else:
        return _error("Cannot change password for legacy accounts.")

    return RedirectResponse(url="/web/", status_code=303)


@auth_router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    token: str = Query(default=""),
    error: str = Query(default=""),
):
    """Register page for invite tokens or first-admin setup."""
    try:
        no_users = not user_db.has_any_users()
    except Exception:
        no_users = False

    if no_users:
        # First-admin setup — no token required
        return templates.TemplateResponse(
            "pages/register.html",
            {
                "request": request,
                "token": "",
                "is_first_admin": True,
                "invite_role": "admin",
                "error": error,
            },
        )

    if not token:
        return RedirectResponse(url="/web/login", status_code=303)

    invite = user_db.validate_invite(token)
    if not invite:
        return templates.TemplateResponse(
            "pages/register.html",
            {
                "request": request,
                "token": token,
                "is_first_admin": False,
                "invite_role": None,
                "error": "This invite link is invalid or has expired.",
            },
        )

    return templates.TemplateResponse(
        "pages/register.html",
        {
            "request": request,
            "token": token,
            "is_first_admin": False,
            "invite_role": invite["role"],
            "error": error,
        },
    )


@auth_router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    token: str = Form(default=""),
):
    """Process registration form."""
    # Validate input
    if len(username.strip()) < 1:
        error = "Username is required"
    elif len(password) < 4:
        error = "Password must be at least 4 characters"
    elif password != password_confirm:
        error = "Passwords do not match"
    else:
        error = ""

    if error:
        try:
            no_users = not user_db.has_any_users()
        except Exception:
            no_users = False
        invite = user_db.validate_invite(token) if token else None
        return templates.TemplateResponse(
            "pages/register.html",
            {
                "request": request,
                "token": token,
                "is_first_admin": no_users,
                "invite_role": invite["role"] if invite else ("admin" if no_users else None),
                "error": error,
            },
            status_code=422,
        )

    username = username.strip()

    try:
        no_users = not user_db.has_any_users()
    except Exception:
        no_users = False

    try:
        if no_users:
            # Create first admin
            new_user = user_db.create_user(username, password, role="admin")
        elif token:
            new_user = user_db.use_invite(token, username, password)
        else:
            raise HTTPException(status_code=403, detail="Registration requires an invite")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("register_submit error: %s", exc)
        return templates.TemplateResponse(
            "pages/register.html",
            {
                "request": request,
                "token": token,
                "is_first_admin": no_users,
                "invite_role": "admin" if no_users else None,
                "error": "An internal error occurred. Please try again.",
            },
            status_code=500,
        )

    if not new_user:
        invite = user_db.validate_invite(token) if token else None
        return templates.TemplateResponse(
            "pages/register.html",
            {
                "request": request,
                "token": token,
                "is_first_admin": no_users,
                "invite_role": invite["role"] if invite else ("admin" if no_users else None),
                "error": "Username already taken or invite is invalid.",
            },
            status_code=422,
        )

    # Log the new user in
    session_token = create_session_token(
        new_user["id"],
        new_user["username"],
        new_user["role"],
        auth_manager.get_secret_key(),
    )
    response = RedirectResponse(url="/web/", status_code=303)
    set_session_cookie(response, session_token)
    return response


# ===== Full Page Routes =====


async def _get_tv_count() -> int | None:
    """Fetch number of series from Sonarr, returns None if unavailable."""
    if not settings.sonarr_url or not settings.sonarr_api_key:
        return None
    client = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
    try:
        series = await client.get_all_series()
        return len(series)
    except Exception:
        return None
    finally:
        await client.close()


async def _get_movie_count() -> int | None:
    """Fetch number of movies from Radarr, returns None if unavailable."""
    if not settings.radarr_url or not settings.radarr_api_key:
        return None
    client = RadarrClient(settings.radarr_url, settings.radarr_api_key)
    try:
        movies = await client.get_all_movies()
        return len(movies)
    except Exception:
        return None
    finally:
        await client.close()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page with overview."""
    services, tv_count, movie_count = await asyncio.gather(
        discover_services(),
        _get_tv_count(),
        _get_movie_count(),
    )
    available_count = sum(1 for s in services.values() if s.available)

    return templates.TemplateResponse(
        "pages/index.html",
        {
            "request": request,
            **_base_ctx(request),
            "services": services,
            "available_count": available_count,
            "total_count": len(services),
            "tv_count": tv_count,
            "movie_count": movie_count,
        },
    )


@router.get("/command", response_class=HTMLResponse)
async def command_page(request: Request):
    """Command input page."""
    return templates.TemplateResponse(
        "pages/command.html",
        {
            "request": request,
            **_base_ctx(request),
        },
    )


@router.get("/services", response_class=HTMLResponse)
async def services_page(request: Request):
    """Services status page."""
    services = await discover_services()

    return templates.TemplateResponse(
        "pages/services.html",
        {
            "request": request,
            **_base_ctx(request),
            "services": services,
        },
    )


@router.get("/library", response_class=HTMLResponse)
async def library_page(
    request: Request,
    media_type: str = Query(default="tv", description="Media type (tv or movie)"),
):
    """Library browser page."""
    return templates.TemplateResponse(
        "pages/library.html",
        {
            "request": request,
            **_base_ctx(request),
            "media_type": media_type,
        },
    )


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    """Search and add page."""
    return templates.TemplateResponse(
        "pages/search.html",
        {
            "request": request,
            **_base_ctx(request),
        },
    )


@router.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    """Help and documentation page."""
    return templates.TemplateResponse(
        "pages/help.html",
        {
            "request": request,
            **_base_ctx(request),
            "version": "0.5.0",
        },
    )


@router.get("/settings", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def settings_page(request: Request):
    """Settings page — admin only."""
    return templates.TemplateResponse(
        "pages/settings.html",
        {
            "request": request,
            **_base_ctx(request),
            "settings": settings,
        },
    )


# ===== Admin Routes =====


@router.get("/admin", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_page(request: Request):
    """Admin panel: user management, invites, pending requests."""
    users = user_db.list_users()
    invites = user_db.list_invites(include_used=False)
    pending = user_db.list_requests(status="pending")

    # Enrich requests with requester username
    user_map = {u["id"]: u["username"] for u in users}
    for req in pending:
        req["requester_name"] = user_map.get(req["requested_by"], "Unknown")

    return templates.TemplateResponse(
        "pages/admin.html",
        {
            "request": request,
            **_base_ctx(request),
            "users": users,
            "invites": invites,
            "pending_requests": pending,
        },
    )


@router.post("/admin/invite/create", response_class=HTMLResponse,
             dependencies=[Depends(require_admin)])
async def admin_create_invite(
    request: Request,
    role: str = Form(default="user"),
    ttl_hours: int = Form(default=48),
):
    """Create an invite link."""
    current_user = get_current_user(request)
    admin_id = current_user["user_id"] if current_user else "system"
    token = user_db.create_invite(role, created_by=admin_id, ttl_hours=ttl_hours)
    invite_url = f"{request.base_url}web/register?token={token}"

    invites = user_db.list_invites(include_used=False)
    return templates.TemplateResponse(
        "partials/invite_list.html",
        {
            "request": request,
            "invites": invites,
            "new_invite_url": invite_url,
            "new_invite_role": role,
        },
    )


@router.post("/admin/invite/delete", response_class=HTMLResponse,
             dependencies=[Depends(require_admin)])
async def admin_delete_invite(
    request: Request,
    token: str = Form(...),
):
    """Delete (revoke) an invite."""
    user_db.delete_invite(token)
    invites = user_db.list_invites(include_used=False)
    return templates.TemplateResponse(
        "partials/invite_list.html",
        {"request": request, "invites": invites},
    )


@router.post("/admin/user/{user_id}/role", response_class=HTMLResponse,
             dependencies=[Depends(require_admin)])
async def admin_set_role(
    request: Request,
    user_id: str,
    role: str = Form(...),
):
    """Change a user's role."""
    current_user = get_current_user(request)
    # Prevent admin from demoting themselves
    if current_user and current_user["user_id"] == user_id and role != "admin":
        pass  # Allow — admin can change their own role if they want
    user_db.update_user(user_id, role=role)
    return templates.TemplateResponse(
        "components/toast.html",
        {"request": request, "type": "success", "message": "Role updated"},
        headers={"HX-Trigger": "user-updated"},
    )


@router.post("/admin/user/{user_id}/toggle", response_class=HTMLResponse,
             dependencies=[Depends(require_admin)])
async def admin_toggle_user(
    request: Request,
    user_id: str,
    enabled: str = Form(...),
):
    """Enable or disable a user account."""
    new_state = enabled.lower() in ("true", "1", "on")
    user_db.update_user(user_id, enabled=1 if new_state else 0)
    label = "enabled" if new_state else "disabled"
    return templates.TemplateResponse(
        "components/toast.html",
        {"request": request, "type": "success", "message": f"User {label}"},
        headers={"HX-Trigger": "user-updated"},
    )


@router.post("/admin/user/{user_id}/delete", response_class=HTMLResponse,
             dependencies=[Depends(require_admin)])
async def admin_delete_user(
    request: Request,
    user_id: str,
):
    """Delete a user account."""
    current_user = get_current_user(request)
    if current_user and current_user["user_id"] == user_id:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": "Cannot delete your own account"},
        )
    user_db.delete_user(user_id)
    return templates.TemplateResponse(
        "components/toast.html",
        {"request": request, "type": "success", "message": "User deleted"},
        headers={"HX-Trigger": "user-updated"},
    )


# ===== Requests Routes =====


@router.get("/requests", response_class=HTMLResponse)
async def requests_page(request: Request):
    """Media requests page — all users can view and submit."""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/web/login", status_code=303)

    role = current_user.get("role", "user")
    if role in ("admin", "power_user"):
        all_requests = user_db.list_requests()
        # Enrich with usernames
        users = {u["id"]: u["username"] for u in user_db.list_users()}
        for req in all_requests:
            req["requester_name"] = users.get(req["requested_by"], "Unknown")
            if req.get("resolved_by"):
                req["resolver_name"] = users.get(req["resolved_by"], "Unknown")
            else:
                req["resolver_name"] = None
    else:
        all_requests = user_db.list_requests(user_id=current_user["user_id"])
        for req in all_requests:
            req["requester_name"] = current_user["username"]
            req["resolver_name"] = None

    return templates.TemplateResponse(
        "pages/requests.html",
        {
            "request": request,
            **_base_ctx(request),
            "requests": all_requests,
            "current_user": current_user,
        },
    )


@router.post("/requests/new", response_class=HTMLResponse)
async def new_request(
    request: Request,
    title: str = Form(...),
    request_type: str = Form(default="media"),
    details: str = Form(default=""),
    media_type: str = Form(default=""),
):
    """Submit a new media request or issue report."""
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    req = user_db.create_request(
        request_type=request_type,
        user_id=current_user["user_id"],
        title=title,
        details=details,
        media_type=media_type,
    )
    try:
        notify_request_submitted(req, settings)
    except Exception as e:
        logger.warning("Failed to send request notification: %s", e)

    return templates.TemplateResponse(
        "components/toast.html",
        {
            "request": request,
            "type": "success",
            "message": f"Request submitted: '{title}'",
        },
        headers={"HX-Trigger": "request-updated"},
    )


@router.post("/requests/{req_id}/resolve", response_class=HTMLResponse)
async def resolve_request(
    request: Request,
    req_id: str,
    status: str = Form(...),
    notes: str = Form(default=""),
):
    """Approve, complete, or reject a request — admin/power_user only."""
    current_user = get_current_user(request)
    if not current_user or current_user.get("role") not in ("admin", "power_user"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    req = user_db.get_request(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    user_db.update_request(req_id, status=status, resolved_by=current_user["user_id"], notes=notes)
    updated_req = user_db.get_request(req_id)
    if updated_req:
        try:
            notify_request_resolved(updated_req, settings)
        except Exception as e:
            logger.warning("Failed to send resolve notification: %s", e)

    return templates.TemplateResponse(
        "components/toast.html",
        {
            "request": request,
            "type": "success",
            "message": f"Request marked as {status}",
        },
        headers={"HX-Trigger": "request-updated"},
    )


# ===== Notification Routes =====


@router.get("/notifications", response_class=HTMLResponse)
async def notifications_panel(request: Request):
    """HTMX partial: notification dropdown panel."""
    current_user = get_current_user(request)
    if not current_user or current_user.get("user_id") == "legacy":
        return templates.TemplateResponse(
            "partials/notifications_panel.html",
            {"request": request, "notifications": [], "unread_count": 0},
        )
    notifications = user_db.get_notifications(current_user["user_id"])
    unread = sum(1 for n in notifications if not n["read"])
    return templates.TemplateResponse(
        "partials/notifications_panel.html",
        {
            "request": request,
            "notifications": notifications,
            "unread_count": unread,
        },
    )


@router.get("/notifications/count", response_class=HTMLResponse)
async def notifications_count(request: Request):
    """HTMX partial: just the unread badge count (polled every 30s)."""
    current_user = get_current_user(request)
    unread = 0
    if current_user and current_user.get("user_id") not in (None, "legacy"):
        try:
            unread = user_db.get_unread_count(current_user["user_id"])
        except Exception:
            pass
    return templates.TemplateResponse(
        "partials/notification_count.html",
        {"request": request, "unread_count": unread},
    )


@router.post("/notifications/read", response_class=HTMLResponse)
async def mark_notifications_read(request: Request):
    """Mark all notifications as read."""
    current_user = get_current_user(request)
    if current_user and current_user.get("user_id") not in (None, "legacy"):
        try:
            user_db.mark_notifications_read(current_user["user_id"])
        except Exception:
            pass
    return templates.TemplateResponse(
        "partials/notifications_panel.html",
        {"request": request, "notifications": [], "unread_count": 0},
    )


# ===== Settings Auth Actions =====


@router.post("/settings/auth/set", response_class=HTMLResponse,
             dependencies=[Depends(require_admin)])
async def auth_set(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
):
    """Set or replace auth credentials."""
    error = None
    if len(username.strip()) < 1:
        error = "Username is required"
    elif len(password) < 4:
        error = "Password must be at least 4 characters"
    elif password != password_confirm:
        error = "Passwords do not match"

    if error:
        return templates.TemplateResponse(
            "partials/auth_settings.html",
            {"request": request, "auth_error": error},
        )

    auth_manager.set_credentials(username.strip(), password)

    # Set session cookie so the user stays logged in
    token = create_session_token(
        "legacy", username.strip(), "admin", auth_manager.get_secret_key()
    )
    response = templates.TemplateResponse(
        "partials/auth_settings.html",
        {"request": request, "auth_success": "Authentication enabled"},
    )
    set_session_cookie(response, token)
    return response


@router.post("/settings/auth/enable", response_class=HTMLResponse,
             dependencies=[Depends(require_admin)])
async def auth_enable(request: Request):
    """Re-enable auth."""
    auth_manager.enable()

    username = auth_manager.get_username()
    if username:
        token = create_session_token(
            "legacy", username, "admin", auth_manager.get_secret_key()
        )
        response = templates.TemplateResponse(
            "partials/auth_settings.html",
            {"request": request, "auth_success": "Authentication re-enabled"},
        )
        set_session_cookie(response, token)
        return response

    return templates.TemplateResponse(
        "partials/auth_settings.html",
        {"request": request, "auth_success": "Authentication re-enabled"},
    )


@router.post("/settings/auth/disable", response_class=HTMLResponse,
             dependencies=[Depends(require_admin)])
async def auth_disable(request: Request):
    """Disable auth without deleting credentials."""
    auth_manager.disable()
    return templates.TemplateResponse(
        "partials/auth_settings.html",
        {"request": request, "auth_success": "Authentication disabled"},
    )


@router.post("/settings/auth/delete", response_class=HTMLResponse,
             dependencies=[Depends(require_admin)])
async def auth_delete(request: Request):
    """Delete all credentials."""
    auth_manager.delete()
    response = templates.TemplateResponse(
        "partials/auth_settings.html",
        {"request": request, "auth_success": "Credentials deleted"},
    )
    clear_session_cookie(response)
    return response


# ===== Service Settings =====


@router.post("/settings/services", response_class=HTMLResponse,
             dependencies=[Depends(require_admin)])
async def save_services(request: Request):
    """Save service URLs and API keys to persistent config."""
    try:
        form = await request.form()
        save_service_config({k: v for k, v in form.multi_items()})
        reset_parser()
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "success", "message": "Settings saved"},
        )
    except Exception as e:
        logger.error("Failed to save service config: %s", e)
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": f"Failed to save: {e}"},
        )


# ===== Notification Webhook Test Routes =====


@router.post("/settings/notifications/test/slack", response_class=HTMLResponse,
             dependencies=[Depends(require_admin)])
async def test_slack_webhook(request: Request):
    """Send a test Slack notification."""
    from ...auth.notifications import send_slack
    if not settings.slack_webhook_url:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": "No Slack webhook configured"},
        )
    ok = send_slack(settings.slack_webhook_url, "Arrmate test notification", title="Test")
    return templates.TemplateResponse(
        "components/toast.html",
        {
            "request": request,
            "type": "success" if ok else "error",
            "message": "Slack test sent!" if ok else "Slack test failed — check webhook URL",
        },
    )


@router.post("/settings/notifications/test/discord", response_class=HTMLResponse,
             dependencies=[Depends(require_admin)])
async def test_discord_webhook(request: Request):
    """Send a test Discord notification."""
    from ...auth.notifications import send_discord
    if not settings.discord_webhook_url:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": "No Discord webhook configured"},
        )
    ok = send_discord(settings.discord_webhook_url, "Arrmate test notification", title="Test")
    return templates.TemplateResponse(
        "components/toast.html",
        {
            "request": request,
            "type": "success" if ok else "error",
            "message": "Discord test sent!" if ok else "Discord test failed — check webhook URL",
        },
    )


# ===== HTMX Partial Routes =====


@router.post("/command/parse", response_class=HTMLResponse)
async def parse_command(request: Request, command: str = Form(...)):
    """Parse command and return preview HTML."""
    try:
        cmd_parser = await get_parser()
        intent = await cmd_parser.parse(command)

        return templates.TemplateResponse(
            "partials/command_preview.html",
            {
                "request": request,
                "intent": intent,
                "command": command,
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            "partials/command_preview.html",
            {
                "request": request,
                "error": str(e),
                "command": command,
            },
        )


@router.post("/command/execute", response_class=HTMLResponse)
async def execute_command(
    request: Request,
    command: str = Form(...),
    mode: str = Form(default=""),
):
    """Execute command and return result HTML with toast.

    mode: optional override — "transcode" to run FFmpeg instead of Sonarr/Radarr search.
    'user' role cannot execute REMOVE or DELETE actions.
    """
    current_user = get_current_user(request)
    user_role = current_user.get("role", "user") if current_user else "user"

    try:
        # Parse
        cmd_parser = await get_parser()
        intent = await cmd_parser.parse(command)

        # Enrich
        intent_engine = get_engine()
        enriched = await intent_engine.enrich(intent)

        # If the user explicitly chose transcode mode, override the action
        if mode == "transcode":
            enriched.action = ActionType.TRANSCODE

        # Role-based action restriction: 'user' cannot delete/remove
        if user_role == "user" and enriched.action in _USER_BLOCKED_ACTIONS:
            return templates.TemplateResponse(
                "partials/execution_result.html",
                {
                    "request": request,
                    "result": {
                        "success": False,
                        "message": "You don't have permission to remove or delete media. "
                                   "Submit a request instead.",
                        "errors": ["Insufficient permissions for this action"],
                    },
                    "show_toast": True,
                    "toast_type": "error",
                    "toast_message": "Permission denied: cannot remove media",
                },
            )

        # Validate
        errors = intent_engine.validate(enriched)
        if errors:
            return templates.TemplateResponse(
                "partials/execution_result.html",
                {
                    "request": request,
                    "result": {
                        "success": False,
                        "message": "Validation failed",
                        "errors": errors,
                    },
                    "show_toast": True,
                    "toast_type": "error",
                    "toast_message": "Validation failed: " + "; ".join(errors),
                },
            )

        # Execute
        exec_engine = get_executor()
        result = await exec_engine.execute(enriched)

        return templates.TemplateResponse(
            "partials/execution_result.html",
            {
                "request": request,
                "result": result,
                "show_toast": True,
                "toast_type": "success" if result.success else "error",
                "toast_message": result.message,
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            "partials/execution_result.html",
            {
                "request": request,
                "result": {
                    "success": False,
                    "message": f"Error: {str(e)}",
                    "errors": [str(e)],
                },
                "show_toast": True,
                "toast_type": "error",
                "toast_message": f"Error: {str(e)}",
            },
        )


@router.get("/services/refresh", response_class=HTMLResponse)
async def refresh_services(request: Request):
    """Refresh service status and return updated HTML."""
    services = await discover_services()

    return templates.TemplateResponse(
        "partials/service_list.html",
        {
            "request": request,
            "services": services,
        },
    )


@router.get("/library/items", response_class=HTMLResponse)
async def library_items(
    request: Request,
    media_type: str = Query(default="tv"),
    page: int = Query(default=1, ge=1),
):
    """Get paginated library items."""
    items = []
    has_more = False
    page_size = 50

    try:
        client = get_client_for_media_type(media_type)
        try:
            if media_type == "tv":
                raw_items = await client.get_all_series()
                for item in raw_items:
                    item_id = item.get("id")
                    poster_url = None
                    for img in item.get("images", []):
                        if img.get("coverType") == "poster":
                            poster_url = img.get("remoteUrl") or f"/web/library/poster/sonarr/{item_id}"
                            break
                    if not poster_url and item_id:
                        poster_url = f"/web/library/poster/sonarr/{item_id}"
                    stats = item.get("statistics", {})
                    items.append({
                        "id": item_id,
                        "title": item.get("title", "Unknown"),
                        "media_type": "tv",
                        "monitored": item.get("monitored", False),
                        "status": item.get("status", ""),
                        "season_count": item.get("seasonCount") or stats.get("seasonCount"),
                        "episode_count": stats.get("episodeFileCount") or item.get("episodeCount"),
                        "year": item.get("year"),
                        "poster_url": poster_url,
                        "size": _format_size(stats.get("sizeOnDisk", 0)),
                        "rating": item.get("ratings", {}).get("value"),
                        "genres": item.get("genres", [])[:3],
                    })
            elif media_type == "movie":
                raw_items = await client.get_all_movies()
                for item in raw_items:
                    item_id = item.get("id")
                    poster_url = None
                    for img in item.get("images", []):
                        if img.get("coverType") == "poster":
                            poster_url = img.get("remoteUrl") or f"/web/library/poster/radarr/{item_id}"
                            break
                    if not poster_url and item_id:
                        poster_url = f"/web/library/poster/radarr/{item_id}"
                    items.append({
                        "id": item_id,
                        "title": item.get("title", "Unknown"),
                        "media_type": "movie",
                        "monitored": item.get("monitored", False),
                        "status": item.get("status", ""),
                        "year": item.get("year"),
                        "size": _format_size(item.get("sizeOnDisk", 0)),
                        "poster_url": poster_url,
                        "rating": item.get("ratings", {}).get("imdb", {}).get("value")
                                  or item.get("ratings", {}).get("value"),
                        "genres": item.get("genres", [])[:3],
                        "has_file": item.get("hasFile", False),
                    })
        finally:
            await client.close()

        items.sort(key=lambda x: x["title"].lower())
        start = (page - 1) * page_size
        end = start + page_size
        has_more = end < len(items)
        items = items[start:end]

    except ValueError as e:
        logger.debug(f"Service not configured for {media_type}: {e}")
    except Exception as e:
        logger.error(f"Error fetching library items: {e}")

    return templates.TemplateResponse(
        "partials/library_list.html",
        {
            "request": request,
            "items": items,
            "media_type": media_type,
            "page": page,
            "has_more": has_more,
            **_base_ctx(request),
        },
    )


@router.get("/search/results", response_class=HTMLResponse)
async def search_results(
    request: Request,
    query: str = Query(..., min_length=1),
    media_type: str = Query(default="tv"),
):
    """Search for media and return results HTML."""
    results = []

    try:
        client = get_client_for_media_type(media_type)
        try:
            raw_results = await client.search(query)
            for item in raw_results[:20]:
                result = {
                    "title": item.get("title", "Unknown"),
                    "media_type": media_type,
                    "year": item.get("year"),
                    "overview": item.get("overview", ""),
                    "status": item.get("status", ""),
                    "poster_url": None,
                    "network": item.get("network"),
                    "rating": None,
                    "quality_profiles": None,
                }

                images = item.get("images") or item.get("remotePoster")
                if isinstance(images, list):
                    for img in images:
                        if img.get("coverType") == "poster":
                            result["poster_url"] = img.get("remoteUrl") or img.get("url")
                            break
                elif isinstance(images, str):
                    result["poster_url"] = images

                ratings = item.get("ratings")
                if ratings and isinstance(ratings, dict):
                    value = ratings.get("value")
                    if value:
                        result["rating"] = f"{value:.1f}"

                results.append(result)
        finally:
            await client.close()

    except ValueError as e:
        logger.debug(f"Service not configured for {media_type}: {e}")
    except Exception as e:
        logger.error(f"Error searching: {e}")

    return templates.TemplateResponse(
        "partials/search_results.html",
        {
            "request": request,
            "results": results,
            "query": query,
            "media_type": media_type,
            **_base_ctx(request),
        },
    )


@router.post("/library/add", response_class=HTMLResponse)
async def add_to_library(
    request: Request,
    title: str = Form(...),
    media_type: str = Form(...),
):
    """Add item to library and return success toast."""
    try:
        client = get_client_for_media_type(media_type)
        try:
            results = await client.search(title)
            if not results:
                return templates.TemplateResponse(
                    "components/toast.html",
                    {
                        "request": request,
                        "type": "error",
                        "message": f"Could not find '{title}' to add",
                    },
                )

            profiles = await client.get_quality_profiles()
            root_folders = await client.get_root_folders()

            if not profiles or not root_folders:
                return templates.TemplateResponse(
                    "components/toast.html",
                    {
                        "request": request,
                        "type": "error",
                        "message": "No quality profiles or root folders configured in your service",
                    },
                )

            profile_id = profiles[0]["id"]
            root_folder = root_folders[0]["path"]
            item = results[0]

            if media_type == "tv":
                await client.add_series(
                    tvdb_id=item["tvdbId"],
                    title=item["title"],
                    quality_profile_id=profile_id,
                    root_folder_path=root_folder,
                )
            elif media_type == "movie":
                await client.add_movie(
                    tmdb_id=item["tmdbId"],
                    title=item["title"],
                    quality_profile_id=profile_id,
                    root_folder_path=root_folder,
                )

            return templates.TemplateResponse(
                "components/toast.html",
                {
                    "request": request,
                    "type": "success",
                    "message": f"Added '{item['title']}' to library",
                },
                headers={"HX-Trigger": "library-updated"},
            )
        finally:
            await client.close()

    except ValueError as e:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": str(e)},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "error",
                "message": f"Failed to add '{title}': {str(e)}",
            },
        )


@router.get("/transcode", response_class=HTMLResponse, dependencies=[Depends(require_power_user)])
async def transcode_page(request: Request):
    """Transcode job status page."""
    jobs = get_all_jobs()
    return templates.TemplateResponse(
        "pages/transcode.html",
        {"request": request, **_base_ctx(request), "jobs": jobs},
    )


@router.get("/transcode/status", response_class=HTMLResponse)
async def transcode_status(request: Request):
    """HTMX partial: live job status panel (auto-refreshes while jobs are running)."""
    jobs = get_all_jobs()
    return templates.TemplateResponse(
        "partials/transcode_status.html",
        {"request": request, "jobs": jobs},
    )


@router.post("/transcode/cancel/{job_id}", response_class=HTMLResponse)
async def transcode_cancel(request: Request, job_id: str):
    """Cancel a running transcode job."""
    ok = cancel_job(job_id)
    jobs = get_all_jobs()
    return templates.TemplateResponse(
        "partials/transcode_status.html",
        {
            "request": request,
            "jobs": jobs,
            "toast_message": f"Job {job_id} cancellation requested." if ok else f"Job {job_id} not found.",
            "toast_type": "success" if ok else "error",
        },
    )


# ===== Plex Hub =====

BUTLER_TASKS = [
    {"name": "CleanOldBundles", "label": "Clean Old Bundles", "desc": "Remove unused bundle data"},
    {"name": "CleanOldCacheFiles", "label": "Clean Cache Files", "desc": "Delete stale cached files"},
    {"name": "BackupDatabase", "label": "Backup Database", "desc": "Back up the Plex database"},
    {"name": "DeepMediaAnalysis", "label": "Deep Media Analysis", "desc": "Re-analyse loudness & bitrate"},
    {"name": "RefreshLocalMedia", "label": "Refresh Local Media", "desc": "Scan for local metadata/artwork"},
    {"name": "SearchForSubtitles", "label": "Search for Subtitles", "desc": "Find missing subtitle files"},
    {"name": "GenerateAutoTags", "label": "Generate Auto Tags", "desc": "Auto-tag music files"},
    {"name": "UpgradeMediaAnalysis", "label": "Upgrade Media Analysis", "desc": "Update media analysis data"},
    {"name": "GenerateChapterImageThumbnails", "label": "Chapter Thumbnails", "desc": "Generate chapter image thumbnails"},
]


def _plex_client() -> PlexClient | None:
    """Return a PlexClient if Plex is configured, else None."""
    if settings.plex_url and settings.plex_token:
        return PlexClient(settings.plex_url, settings.plex_token)
    return None


def _plex_tv_client() -> PlexTVClient | None:
    """Return a PlexTVClient if Plex token is available, else None."""
    if settings.plex_token:
        return PlexTVClient(settings.plex_token)
    return None


def _plex_thumb_url(path: str) -> str:
    """Build a proxied Plex thumbnail URL (keeps token server-side)."""
    import urllib.parse
    return f"/web/plex/thumb?path={urllib.parse.quote(path, safe='')}"


@router.get("/plex", response_class=HTMLResponse)
async def plex_page(request: Request):
    """Plex hub page."""
    plex = _plex_client()
    configured = plex is not None
    accounts = []
    if plex:
        try:
            accounts = await plex.get_accounts()
        except Exception:
            pass
        finally:
            await plex.close()
    return templates.TemplateResponse(
        "pages/plex.html",
        {
            "request": request,
            **_base_ctx(request),
            "configured": configured,
            "accounts": accounts,
            "butler_tasks": BUTLER_TASKS,
        },
    )


@router.get("/plex/thumb", response_class=HTMLResponse)
async def plex_thumb(path: str = Query(...)):
    """Proxy a Plex thumbnail image (keeps token server-side)."""
    import httpx as _httpx
    from fastapi.responses import Response as _Response

    if not settings.plex_url or not settings.plex_token:
        return _Response(status_code=404)
    url = f"{settings.plex_url.rstrip('/')}{path}"
    try:
        async with _httpx.AsyncClient(timeout=10) as hx:
            resp = await hx.get(
                url,
                headers={
                    "X-Plex-Token": settings.plex_token,
                    "Accept": "image/jpeg,image/*",
                },
            )
            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "image/jpeg")
                return _Response(content=resp.content, media_type=ct)
    except Exception:
        pass
    return _Response(status_code=404)


@router.get("/plex/history", response_class=HTMLResponse)
async def plex_history(
    request: Request,
    account_id: int = Query(default=0),
    days: int = Query(default=7, ge=0),  # 0 = all time
):
    """HTMX partial: watch history."""
    import time as _time
    cutoff = int(_time.time()) - (days * 86400) if days > 0 else 0
    # Fetch more items when a short window is selected so we don't miss entries
    fetch_limit = 500 if days > 0 else 200

    items = []
    error = None
    plex = _plex_client()
    if plex:
        try:
            raw = await plex.get_history(
                account_id=account_id if account_id else None,
                limit=fetch_limit,
            )
            for item in raw:
                viewed_at = item.get("viewedAt", 0)
                # Skip items with no timestamp
                if viewed_at == 0:
                    continue
                # Skip items older than the cutoff (don't break — multi-user results
                # may not be strictly newest-first across all accounts)
                if cutoff and viewed_at < cutoff:
                    continue
                media_type = item.get("type", "")
                if media_type == "episode":
                    show = item.get("grandparentTitle") or item.get("title") or ""
                    ep_title = item.get("title", "")
                    title = f"{show} — {ep_title}" if show else ep_title
                    subtitle = f"S{item.get('parentIndex', 0):02d}E{item.get('index', 0):02d}"
                else:
                    title = item.get("title") or ""
                    subtitle = str(item.get("year", "")) if item.get("year") else ""
                # Skip entries with no usable title (e.g. media removed from library)
                if not title:
                    continue
                thumb = _plex_thumb_url(item.get("thumb", "")) if item.get("thumb") else None
                user_info = item.get("User", {})
                items.append({
                    "title": title,
                    "subtitle": subtitle,
                    "type": media_type,
                    "viewed_at": viewed_at,
                    "thumb": thumb,
                    "rating_key": item.get("ratingKey"),
                    "user": user_info.get("title", "") if isinstance(user_info, dict) else "",
                })
        except Exception as e:
            error = str(e)
        finally:
            await plex.close()
    else:
        error = "Plex is not configured"
    return templates.TemplateResponse(
        "partials/plex_history.html",
        {"request": request, "items": items, "error": error, "days": days},
    )


@router.get("/plex/continue", response_class=HTMLResponse)
async def plex_continue_watching(request: Request):
    """HTMX partial: continue watching list."""
    items = []
    error = None
    plex = _plex_client()
    if plex:
        try:
            raw = await plex.get_continue_watching()
            for item in raw:
                duration = item.get("duration", 0)
                offset = item.get("viewOffset", 0)
                pct = int(offset / duration * 100) if duration else 0
                media_type = item.get("type", "")
                if media_type == "episode":
                    title = item.get("grandparentTitle", item.get("title", "Unknown"))
                    subtitle = f"S{item.get('parentIndex', 0):02d}E{item.get('index', 0):02d} — {item.get('title', '')}"
                else:
                    title = item.get("title", "Unknown")
                    subtitle = str(item.get("year", "")) if item.get("year") else ""
                thumb = item.get("thumb") or item.get("grandparentThumb")
                items.append({
                    "title": title,
                    "subtitle": subtitle,
                    "type": media_type,
                    "pct": pct,
                    "thumb": _plex_thumb_url(thumb) if thumb else None,
                    "rating_key": item.get("ratingKey"),
                    "year": item.get("year"),
                })
        except Exception as e:
            error = str(e)
        finally:
            await plex.close()
    else:
        error = "Plex is not configured"
    return templates.TemplateResponse(
        "partials/plex_continue.html",
        {"request": request, "items": items, "error": error},
    )


@router.get("/plex/ondeck", response_class=HTMLResponse)
async def plex_on_deck(request: Request):
    """HTMX partial: on deck items."""
    items = []
    error = None
    plex = _plex_client()
    if plex:
        try:
            raw = await plex.get_on_deck()
            for item in raw:
                media_type = item.get("type", "")
                if media_type == "episode":
                    title = item.get("grandparentTitle", item.get("title", "Unknown"))
                    subtitle = f"S{item.get('parentIndex', 0):02d}E{item.get('index', 0):02d} — {item.get('title', '')}"
                else:
                    title = item.get("title", "Unknown")
                    subtitle = ""
                thumb = item.get("thumb") or item.get("grandparentThumb")
                items.append({
                    "title": title,
                    "subtitle": subtitle,
                    "type": media_type,
                    "thumb": _plex_thumb_url(thumb) if thumb else None,
                    "rating_key": item.get("ratingKey"),
                    "year": item.get("year"),
                    "summary": item.get("summary", "")[:120],
                })
        except Exception as e:
            error = str(e)
        finally:
            await plex.close()
    else:
        error = "Plex is not configured"
    return templates.TemplateResponse(
        "partials/plex_ondeck.html",
        {"request": request, "items": items, "error": error},
    )


@router.get("/plex/recent", response_class=HTMLResponse)
async def plex_recently_added(
    request: Request,
    limit: int = Query(default=25, le=100),
):
    """HTMX partial: recently added items."""
    items = []
    error = None
    plex = _plex_client()
    if plex:
        try:
            raw = await plex.get_recently_added(limit=limit)
            for item in raw:
                media_type = item.get("type", "")
                if media_type == "episode":
                    title = item.get("grandparentTitle", item.get("title", "Unknown"))
                    subtitle = f"S{item.get('parentIndex', 0):02d}E{item.get('index', 0):02d} — {item.get('title', '')}"
                elif media_type == "season":
                    title = item.get("parentTitle", item.get("title", "Unknown"))
                    subtitle = item.get("title", "")
                else:
                    title = item.get("title", "Unknown")
                    subtitle = str(item.get("year", "")) if item.get("year") else ""
                thumb = item.get("thumb") or item.get("grandparentThumb")
                items.append({
                    "title": title,
                    "subtitle": subtitle,
                    "type": media_type,
                    "thumb": _plex_thumb_url(thumb) if thumb else None,
                    "rating_key": item.get("ratingKey"),
                    "year": item.get("year"),
                    "added_at": item.get("addedAt", 0),
                })
        except Exception as e:
            error = str(e)
        finally:
            await plex.close()
    else:
        error = "Plex is not configured"
    return templates.TemplateResponse(
        "partials/plex_recent.html",
        {"request": request, "items": items, "error": error},
    )


@router.get("/plex/butler", response_class=HTMLResponse)
async def plex_butler(request: Request):
    """HTMX partial: Butler task list with run buttons."""
    tasks = []
    error = None
    plex = _plex_client()
    if plex:
        try:
            api_tasks = await plex.get_butler_tasks()
            api_map = {t.get("name"): t for t in api_tasks}
            for bt in BUTLER_TASKS:
                api = api_map.get(bt["name"], {})
                tasks.append({
                    "name": bt["name"],
                    "label": bt["label"],
                    "desc": bt["desc"],
                    "running": api.get("running", False),
                    "enabled": api.get("enabled", True),
                })
        except Exception as e:
            error = str(e)
        finally:
            await plex.close()
    else:
        error = "Plex is not configured"
    return templates.TemplateResponse(
        "partials/plex_butler.html",
        {"request": request, "tasks": tasks, "error": error},
    )


@router.post("/plex/butler/{task_name}", response_class=HTMLResponse)
async def run_plex_butler_task(request: Request, task_name: str):
    """Run a Plex Butler maintenance task."""
    plex = _plex_client()
    if not plex:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": "Plex is not configured"},
        )
    try:
        ok = await plex.run_butler_task(task_name)
        label = next((t["label"] for t in BUTLER_TASKS if t["name"] == task_name), task_name)
        msg_type = "success" if ok else "error"
        msg = f"Started: {label}" if ok else f"Failed to start: {label}"
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": msg_type, "message": msg},
        )
    finally:
        await plex.close()


@router.delete("/plex/session/{session_key}", response_class=HTMLResponse)
async def terminate_plex_session(
    request: Request,
    session_key: str,
    reason: str = Query(default="Session terminated by Arrmate"),
):
    """Terminate an active Plex streaming session."""
    plex = _plex_client()
    if not plex:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": "Plex is not configured"},
        )
    try:
        ok = await plex.terminate_session(session_key, reason)
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "success" if ok else "error",
                "message": "Session terminated" if ok else "Failed to terminate session",
            },
            headers={"HX-Trigger": "plex-session-terminated"},
        )
    finally:
        await plex.close()


@router.post("/plex/rate", response_class=HTMLResponse)
async def rate_plex_item(
    request: Request,
    rating_key: str = Form(...),
    stars: float = Form(...),
    title: str = Form(default=""),
):
    """Rate a Plex item (1-5 stars) from the UI."""
    plex = _plex_client()
    if not plex:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": "Plex is not configured"},
        )
    try:
        ok = await plex.rate_item(rating_key, stars)
        label = title or rating_key
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "success" if ok else "error",
                "message": f"Rated '{label}' {int(stars)} ★" if ok else f"Failed to rate '{label}'",
            },
        )
    finally:
        await plex.close()


@router.post("/plex/detect/{rating_key}/intro", response_class=HTMLResponse)
async def plex_detect_intro(request: Request, rating_key: str):
    """Trigger Plex intro detection for an item."""
    plex = _plex_client()
    if not plex:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": "Plex is not configured"},
        )
    try:
        ok = await plex.detect_intro(rating_key)
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "success" if ok else "error",
                "message": "Intro detection queued" if ok else "Failed to queue intro detection",
            },
        )
    finally:
        await plex.close()


@router.post("/plex/detect/{rating_key}/credits", response_class=HTMLResponse)
async def plex_detect_credits(request: Request, rating_key: str):
    """Trigger Plex credit detection for an item."""
    plex = _plex_client()
    if not plex:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": "Plex is not configured"},
        )
    try:
        ok = await plex.detect_credits(rating_key)
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "success" if ok else "error",
                "message": "Credit detection queued" if ok else "Failed to queue credit detection",
            },
        )
    finally:
        await plex.close()


# ===== Plex Share Server =====


@router.get(
    "/plex/share",
    response_class=HTMLResponse,
    dependencies=[Depends(require_power_user)],
)
async def plex_share_panel(request: Request):
    """HTMX partial: share server management (invite + current shares)."""
    plex = _plex_client()
    plex_tv = _plex_tv_client()

    libraries: list = []
    friends: list = []
    machine_id: str | None = None
    error: str | None = None

    if not plex or not plex_tv:
        error = "Plex is not configured (PLEX_URL and PLEX_TOKEN required)"
    else:
        try:
            machine_id, raw_libs, raw_friends = await asyncio.gather(
                plex.get_machine_identifier(),
                plex.get_libraries(),
                plex_tv.get_friends(),
                return_exceptions=True,
            )
            if isinstance(machine_id, Exception):
                machine_id = None
            if isinstance(raw_libs, Exception):
                raw_libs = []
            if isinstance(raw_friends, Exception):
                raw_friends = []
                error = "Could not load friends list from plex.tv"

            # Build clean library list (key as int for matching)
            for lib in (raw_libs or []):
                libraries.append({
                    "key": int(lib.get("key", 0)),
                    "title": lib.get("title", ""),
                    "type": lib.get("type", ""),
                })

            # Filter friends to those who have access to THIS server
            for f in (raw_friends or []):
                servers = f.get("servers") or []
                on_this_server = any(
                    s.get("machineIdentifier") == machine_id for s in servers
                )
                if on_this_server:
                    server_info = next(
                        (s for s in servers if s.get("machineIdentifier") == machine_id),
                        {},
                    )
                    shared_sections = server_info.get("sections") or []
                    friends.append({
                        "id": f.get("id"),
                        "username": f.get("title") or f.get("username") or "Unknown",
                        "email": f.get("email", ""),
                        "thumb": f.get("thumb", ""),
                        "all_libraries": server_info.get("allLibraries", False),
                        "section_titles": [s.get("title", "") for s in shared_sections],
                    })
        except Exception as e:
            error = str(e)
        finally:
            await plex.close()
            await plex_tv.close()

    return templates.TemplateResponse(
        "partials/plex_share.html",
        {
            "request": request,
            "libraries": libraries,
            "friends": friends,
            "machine_id": machine_id,
            "error": error,
        },
    )


@router.post(
    "/plex/share/invite",
    response_class=HTMLResponse,
    dependencies=[Depends(require_power_user)],
)
async def plex_share_invite(request: Request):
    """Send a Plex server share invite to an email address."""
    form = await request.form()
    email = (form.get("email") or "").strip()
    # section_ids comes as one or more values; empty = share all
    raw_ids = form.getlist("section_ids")
    section_ids = [int(v) for v in raw_ids if v.isdigit()]

    if not email:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": "Email address is required"},
        )

    plex = _plex_client()
    plex_tv = _plex_tv_client()
    if not plex or not plex_tv:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": "Plex is not configured"},
        )

    try:
        machine_id = await plex.get_machine_identifier()
        await plex.close()
        if not machine_id:
            return templates.TemplateResponse(
                "components/toast.html",
                {"request": request, "type": "error", "message": "Could not get Plex server ID"},
            )
        await plex_tv.share_server(machine_id, email, section_ids)
        lib_note = "all libraries" if not section_ids else f"{len(section_ids)} librar{'y' if len(section_ids) == 1 else 'ies'}"
        resp = templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "success", "message": f"Invite sent to {email} ({lib_note})"},
        )
        resp.headers["HX-Trigger"] = "plexShareUpdated"
        return resp
    except Exception as e:
        msg = str(e)
        if "400" in msg:
            msg = "Could not send invite — user may already have access, or email not found on plex.tv"
        elif "401" in msg or "403" in msg:
            msg = "Authentication failed — check your PLEX_TOKEN"
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": msg},
        )
    finally:
        await plex_tv.close()


@router.post(
    "/plex/share/remove/{friend_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(require_power_user)],
)
async def plex_share_remove(request: Request, friend_id: int):
    """Revoke a friend's access to this Plex server."""
    plex_tv = _plex_tv_client()
    if not plex_tv:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": "Plex is not configured"},
        )
    try:
        ok = await plex_tv.remove_friend(friend_id)
        resp = templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "success" if ok else "error",
                "message": "Access revoked" if ok else "Failed to revoke access",
            },
        )
        if ok:
            resp.headers["HX-Trigger"] = "plexShareUpdated"
        return resp
    finally:
        await plex_tv.close()


# ===== Plex Now Playing =====


@router.get("/plex/nowplaying", response_class=HTMLResponse)
async def plex_now_playing(request: Request):
    """HTMX partial: current Plex sessions for the navbar strip."""
    sessions = []
    if settings.plex_url and settings.plex_token:
        client = PlexClient(settings.plex_url, settings.plex_token)
        try:
            raw = await client.get_sessions()
            for s in raw:
                media_type = s.get("type", "")
                if media_type == "episode":
                    title = f"{s.get('grandparentTitle', '')} S{s.get('parentIndex', 0):02d}E{s.get('index', 0):02d}"
                elif media_type == "movie":
                    title = s.get("title", "Unknown")
                else:
                    title = s.get("title", "Unknown")
                duration = s.get("duration", 0)
                offset = s.get("viewOffset", 0)
                pct = int(offset / duration * 100) if duration else 0
                sessions.append({
                    "title": title,
                    "user": s.get("User", {}).get("title", ""),
                    "player": s.get("Player", {}).get("title", ""),
                    "state": s.get("Player", {}).get("state", "playing"),
                    "pct": pct,
                    "type": media_type,
                    "session_key": s.get("sessionKey", ""),
                })
        except Exception:
            pass
        finally:
            await client.close()
    return templates.TemplateResponse(
        "partials/plex_nowplaying.html",
        {"request": request, "sessions": sessions},
    )


# ===== Library action routes =====


@router.post("/library/monitor", response_class=HTMLResponse)
async def toggle_monitor(
    request: Request,
    item_id: int = Form(...),
    media_type: str = Form(...),
    monitored: str = Form(...),
):
    """Toggle monitoring status for a movie or TV series."""
    new_state = monitored.lower() == "true"
    label = "Monitored" if new_state else "Unmonitored"
    try:
        if media_type == "movie":
            client = RadarrClient(settings.radarr_url, settings.radarr_api_key)
            try:
                await client.set_movie_monitored(item_id, new_state)
            finally:
                await client.close()
        elif media_type == "tv":
            client = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
            try:
                await client.set_series_monitored(item_id, new_state)
            finally:
                await client.close()
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "success", "message": f"Set to {label}"},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": str(e)},
        )


@router.post("/library/upgrade", response_class=HTMLResponse)
async def upgrade_item(
    request: Request,
    item_id: int = Form(...),
    media_type: str = Form(...),
    title: str = Form(...),
):
    """Trigger a quality upgrade search for a library item."""
    try:
        if media_type == "movie":
            client = RadarrClient(settings.radarr_url, settings.radarr_api_key)
            try:
                await client.trigger_movie_search(item_id)
            finally:
                await client.close()
            msg = f"Triggered upgrade search for '{title}'"
        elif media_type == "tv":
            client = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
            try:
                await client.trigger_series_search(item_id)
            finally:
                await client.close()
            msg = f"Triggered search for '{title}'"
        else:
            msg = "Unsupported media type"
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "success", "message": msg},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": str(e)},
        )


@router.post("/library/moreseasons", response_class=HTMLResponse)
async def more_seasons(
    request: Request,
    item_id: int = Form(...),
    title: str = Form(...),
):
    """Monitor all seasons of a series and trigger a full search for new episodes."""
    try:
        client = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
        try:
            await client.monitor_all_seasons(item_id)
            await client.trigger_series_search(item_id)
        finally:
            await client.close()
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "success",
             "message": f"All seasons monitored and search triggered for '{title}'"},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": str(e)},
        )


@router.post("/library/remove", response_class=HTMLResponse,
             dependencies=[Depends(require_power_user)])
async def remove_item(
    request: Request,
    item_id: int = Form(...),
    media_type: str = Form(...),
    title: str = Form(...),
):
    """Remove a movie or TV series and delete its files — power_user/admin only."""
    try:
        if media_type == "movie":
            client = RadarrClient(settings.radarr_url, settings.radarr_api_key)
            try:
                await client.delete_item(item_id, delete_files=True)
            finally:
                await client.close()
        elif media_type == "tv":
            client = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
            try:
                await client.delete_item(item_id, delete_files=True)
            finally:
                await client.close()
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "success",
             "message": f"Removed '{title}' and all files"},
            headers={"HX-Trigger": "library-updated"},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": str(e)},
        )


@router.get("/library/poster/{service}/{item_id}", response_class=HTMLResponse)
async def library_poster(service: str, item_id: int):
    """Proxy poster images from Sonarr/Radarr (keeps API key server-side)."""
    import httpx as _httpx
    from fastapi.responses import Response as _Response

    if service == "sonarr" and settings.sonarr_url and settings.sonarr_api_key:
        url = f"{settings.sonarr_url.rstrip('/')}/api/v3/mediacover/{item_id}/poster.jpg"
        headers = {"X-Api-Key": settings.sonarr_api_key}
    elif service == "radarr" and settings.radarr_url and settings.radarr_api_key:
        url = f"{settings.radarr_url.rstrip('/')}/api/v3/mediacover/{item_id}/poster.jpg"
        headers = {"X-Api-Key": settings.radarr_api_key}
    else:
        return _Response(status_code=404)

    try:
        async with _httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return _Response(content=resp.content, media_type="image/jpeg")
    except Exception:
        pass
    return _Response(status_code=404)


# ===== Downloads page =====


@router.get("/downloads", response_class=HTMLResponse, dependencies=[Depends(require_power_user)])
async def downloads_page(request: Request):
    """Download manager overview page."""
    return templates.TemplateResponse(
        "pages/downloads.html",
        {"request": request, **_base_ctx(request)},
    )


@router.get("/downloads/status", response_class=HTMLResponse)
async def downloads_status(request: Request):
    """HTMX partial: live download queue from all configured managers."""
    from ...clients.sabnzbd import SABnzbdClient
    from ...clients.nzbget import NZBgetClient
    from ...clients.qbittorrent import QBittorrentClient
    from ...clients.transmission import TransmissionClient

    managers = []

    if settings.sabnzbd_url and settings.sabnzbd_api_key:
        client = SABnzbdClient(settings.sabnzbd_url, settings.sabnzbd_api_key)
        try:
            status = await client.get_status()
            queue = await client.get_queue()
            managers.append({
                "name": "SABnzbd", "type": "sabnzbd", "status": status, "queue": queue,
            })
        except Exception as e:
            managers.append({"name": "SABnzbd", "type": "sabnzbd", "error": str(e)})
        finally:
            await client.close()

    if settings.nzbget_url and settings.nzbget_username:
        client = NZBgetClient(
            settings.nzbget_url, settings.nzbget_username, settings.nzbget_password or ""
        )
        try:
            status = await client.get_status()
            queue = await client.get_queue()
            managers.append({"name": "NZBget", "type": "nzbget", "status": status, "queue": queue})
        except Exception as e:
            managers.append({"name": "NZBget", "type": "nzbget", "error": str(e)})
        finally:
            await client.close()

    if settings.qbittorrent_url and settings.qbittorrent_username:
        client = QBittorrentClient(
            settings.qbittorrent_url,
            settings.qbittorrent_username,
            settings.qbittorrent_password or "",
        )
        try:
            info = await client.get_transfer_info()
            torrents = await client.get_torrents()
            managers.append({
                "name": "qBittorrent", "type": "qbittorrent",
                "status": info, "queue": torrents,
            })
        except Exception as e:
            managers.append({"name": "qBittorrent", "type": "qbittorrent", "error": str(e)})
        finally:
            await client.close()

    if settings.transmission_url:
        client = TransmissionClient(
            settings.transmission_url,
            settings.transmission_username or "",
            settings.transmission_password or "",
        )
        try:
            session = await client.get_session()
            torrents = await client.get_torrents()
            managers.append({
                "name": "Transmission", "type": "transmission",
                "status": session, "queue": torrents,
            })
        except Exception as e:
            managers.append({"name": "Transmission", "type": "transmission", "error": str(e)})
        finally:
            await client.close()

    return templates.TemplateResponse(
        "partials/downloads_status.html",
        {"request": request, "managers": managers, **_base_ctx(request)},
    )


@router.post("/downloads/speed", response_class=HTMLResponse)
async def set_download_speed(
    request: Request,
    manager: str = Form(...),
    kbps: int = Form(...),
):
    """Set download speed limit for a download manager."""
    from ...clients.sabnzbd import SABnzbdClient
    from ...clients.nzbget import NZBgetClient
    from ...clients.qbittorrent import QBittorrentClient
    from ...clients.transmission import TransmissionClient

    try:
        if manager == "sabnzbd" and settings.sabnzbd_url:
            c = SABnzbdClient(settings.sabnzbd_url, settings.sabnzbd_api_key)
            await c.set_speed_limit(kbps)
            await c.close()
        elif manager == "nzbget" and settings.nzbget_url:
            c = NZBgetClient(settings.nzbget_url, settings.nzbget_username or "", settings.nzbget_password or "")
            await c.set_speed_limit(kbps)
            await c.close()
        elif manager == "qbittorrent" and settings.qbittorrent_url:
            c = QBittorrentClient(settings.qbittorrent_url, settings.qbittorrent_username or "", settings.qbittorrent_password or "")
            await c.set_download_limit(kbps * 1024)
            await c.close()
        elif manager == "transmission" and settings.transmission_url:
            c = TransmissionClient(settings.transmission_url, settings.transmission_username or "", settings.transmission_password or "")
            await c.set_speed_limit_down(kbps)
            await c.close()
        label = "unlimited" if kbps == 0 else f"{kbps} KB/s"
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "success", "message": f"Speed limit set to {label}"},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": str(e)},
        )


# ===== Download Item Control Routes =====


@router.post("/downloads/priority", response_class=HTMLResponse,
             dependencies=[Depends(require_power_user)])
async def set_download_priority(
    request: Request,
    manager: str = Form(...),
    item_id: str = Form(...),
    priority: int = Form(...),
):
    """Set priority for an individual queue item."""
    from ...clients.sabnzbd import SABnzbdClient
    from ...clients.nzbget import NZBgetClient
    from ...clients.transmission import TransmissionClient

    try:
        ok = False
        if manager == "sabnzbd" and settings.sabnzbd_url:
            c = SABnzbdClient(settings.sabnzbd_url, settings.sabnzbd_api_key)
            ok = await c.set_priority(item_id, priority)
            await c.close()
        elif manager == "nzbget" and settings.nzbget_url:
            c = NZBgetClient(
                settings.nzbget_url, settings.nzbget_username or "", settings.nzbget_password or ""
            )
            ok = await c.set_priority(int(item_id), priority)
            await c.close()
        elif manager == "transmission" and settings.transmission_url:
            c = TransmissionClient(
                settings.transmission_url,
                settings.transmission_username or "",
                settings.transmission_password or "",
            )
            ok = await c.set_bandwidth_priority(int(item_id), priority)
            await c.close()
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "success" if ok else "warning",
                "message": "Priority updated" if ok else "Priority update submitted",
            },
            headers={"HX-Trigger": "downloads-updated"},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": str(e)},
        )


@router.post("/downloads/move", response_class=HTMLResponse,
             dependencies=[Depends(require_power_user)])
async def move_download_item(
    request: Request,
    manager: str = Form(...),
    item_id: str = Form(...),
    action: str = Form(...),
):
    """Move a queue item. action: absolute slot for SABnzbd, int offset for NZBget,
    'top'/'bottom'/'increase'/'decrease' for qBittorrent."""
    from ...clients.sabnzbd import SABnzbdClient
    from ...clients.nzbget import NZBgetClient
    from ...clients.qbittorrent import QBittorrentClient

    try:
        ok = False
        if manager == "sabnzbd" and settings.sabnzbd_url:
            c = SABnzbdClient(settings.sabnzbd_url, settings.sabnzbd_api_key)
            ok = await c.move_item(item_id, int(action))
            await c.close()
        elif manager == "nzbget" and settings.nzbget_url:
            c = NZBgetClient(
                settings.nzbget_url, settings.nzbget_username or "", settings.nzbget_password or ""
            )
            ok = await c.move_item(int(item_id), int(action))
            await c.close()
        elif manager == "qbittorrent" and settings.qbittorrent_url:
            c = QBittorrentClient(
                settings.qbittorrent_url,
                settings.qbittorrent_username or "",
                settings.qbittorrent_password or "",
            )
            ok = await c.set_priority(item_id, action)
            await c.close()
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "success" if ok else "warning",
                "message": "Queue order updated" if ok else "Queue move submitted",
            },
            headers={"HX-Trigger": "downloads-updated"},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": str(e)},
        )


@router.post("/downloads/item/pause", response_class=HTMLResponse,
             dependencies=[Depends(require_power_user)])
async def pause_download_item(
    request: Request,
    manager: str = Form(...),
    item_id: str = Form(...),
):
    """Pause an individual queue item (SABnzbd / NZBget)."""
    from ...clients.sabnzbd import SABnzbdClient
    from ...clients.nzbget import NZBgetClient

    try:
        ok = False
        if manager == "sabnzbd" and settings.sabnzbd_url:
            c = SABnzbdClient(settings.sabnzbd_url, settings.sabnzbd_api_key)
            ok = await c.pause_item(item_id)
            await c.close()
        elif manager == "nzbget" and settings.nzbget_url:
            c = NZBgetClient(
                settings.nzbget_url, settings.nzbget_username or "", settings.nzbget_password or ""
            )
            ok = await c.pause_item(int(item_id))
            await c.close()
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "success" if ok else "warning",
                "message": "Item paused" if ok else "Pause submitted",
            },
            headers={"HX-Trigger": "downloads-updated"},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": str(e)},
        )


@router.post("/downloads/item/resume", response_class=HTMLResponse,
             dependencies=[Depends(require_power_user)])
async def resume_download_item(
    request: Request,
    manager: str = Form(...),
    item_id: str = Form(...),
):
    """Resume an individual paused queue item (SABnzbd / NZBget)."""
    from ...clients.sabnzbd import SABnzbdClient
    from ...clients.nzbget import NZBgetClient

    try:
        ok = False
        if manager == "sabnzbd" and settings.sabnzbd_url:
            c = SABnzbdClient(settings.sabnzbd_url, settings.sabnzbd_api_key)
            ok = await c.resume_item(item_id)
            await c.close()
        elif manager == "nzbget" and settings.nzbget_url:
            c = NZBgetClient(
                settings.nzbget_url, settings.nzbget_username or "", settings.nzbget_password or ""
            )
            ok = await c.resume_item(int(item_id))
            await c.close()
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "success" if ok else "warning",
                "message": "Item resumed" if ok else "Resume submitted",
            },
            headers={"HX-Trigger": "downloads-updated"},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": str(e)},
        )


@router.post("/downloads/add", response_class=HTMLResponse,
             dependencies=[Depends(require_power_user)])
async def add_download(
    request: Request,
    manager: str = Form(...),
    url: str = Form(...),
    priority: int = Form(default=0),
    category: str = Form(default=""),
):
    """Add an NZB or torrent/magnet URL directly to a download manager."""
    from ...clients.sabnzbd import SABnzbdClient
    from ...clients.nzbget import NZBgetClient
    from ...clients.qbittorrent import QBittorrentClient
    from ...clients.transmission import TransmissionClient

    try:
        ok = False
        if manager == "sabnzbd" and settings.sabnzbd_url:
            c = SABnzbdClient(settings.sabnzbd_url, settings.sabnzbd_api_key)
            ok = await c.add_url(url, priority=priority, category=category)
            await c.close()
        elif manager == "nzbget" and settings.nzbget_url:
            c = NZBgetClient(
                settings.nzbget_url, settings.nzbget_username or "", settings.nzbget_password or ""
            )
            ok = await c.add_url(url, priority=priority, category=category)
            await c.close()
        elif manager == "qbittorrent" and settings.qbittorrent_url:
            c = QBittorrentClient(
                settings.qbittorrent_url,
                settings.qbittorrent_username or "",
                settings.qbittorrent_password or "",
            )
            ok = await c.add_url(url, category=category)
            await c.close()
        elif manager == "transmission" and settings.transmission_url:
            c = TransmissionClient(
                settings.transmission_url,
                settings.transmission_username or "",
                settings.transmission_password or "",
            )
            ok = await c.add_url(url)
            await c.close()
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "success" if ok else "warning",
                "message": "Download added" if ok else "Download submitted",
            },
            headers={"HX-Trigger": "downloads-updated"},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": str(e)},
        )


# ===== Prowlarr Routes =====


def _prowlarr_client():
    """Return ProwlarrClient if configured, else None."""
    if settings.prowlarr_url and settings.prowlarr_api_key:
        from ...clients.prowlarr import ProwlarrClient
        return ProwlarrClient(settings.prowlarr_url, settings.prowlarr_api_key)
    return None


@router.get("/prowlarr", response_class=HTMLResponse)
async def prowlarr_page(request: Request):
    """Prowlarr indexer search page."""
    client = _prowlarr_client()
    configured = client is not None
    indexers = []
    if client:
        try:
            indexers = await client.get_indexers()
        except Exception:
            pass
        finally:
            await client.close()
    return templates.TemplateResponse(
        "pages/prowlarr.html",
        {
            "request": request,
            **_base_ctx(request),
            "configured": configured,
            "indexers": indexers,
        },
    )


@router.get("/prowlarr/search", response_class=HTMLResponse)
async def prowlarr_search(
    request: Request,
    query: str = Query(default=""),
    categories: str = Query(default=""),
):
    """HTMX partial: Prowlarr indexer search results."""
    client = _prowlarr_client()
    results = []
    error = None

    if not client:
        error = "Prowlarr is not configured (set PROWLARR_URL and PROWLARR_API_KEY)"
    elif query:
        try:
            cat_ids = [int(c) for c in categories.split(",") if c.strip().isdigit()] if categories else None
            results = await client.search(query, categories=cat_ids)
        except Exception as e:
            error = str(e)
        finally:
            await client.close()

    return templates.TemplateResponse(
        "partials/prowlarr_results.html",
        {
            "request": request,
            "results": results,
            "query": query,
            "error": error,
            **_base_ctx(request),
        },
    )


@router.post("/prowlarr/send", response_class=HTMLResponse,
             dependencies=[Depends(require_power_user)])
async def prowlarr_send(
    request: Request,
    url: str = Form(...),
    manager: str = Form(...),
    title: str = Form(default=""),
):
    """Send a Prowlarr search result URL to a configured download manager."""
    from ...clients.sabnzbd import SABnzbdClient
    from ...clients.nzbget import NZBgetClient
    from ...clients.qbittorrent import QBittorrentClient
    from ...clients.transmission import TransmissionClient

    try:
        ok = False
        if manager == "sabnzbd" and settings.sabnzbd_url:
            c = SABnzbdClient(settings.sabnzbd_url, settings.sabnzbd_api_key)
            ok = await c.add_url(url)
            await c.close()
        elif manager == "nzbget" and settings.nzbget_url:
            c = NZBgetClient(
                settings.nzbget_url, settings.nzbget_username or "", settings.nzbget_password or ""
            )
            ok = await c.add_url(url)
            await c.close()
        elif manager == "qbittorrent" and settings.qbittorrent_url:
            c = QBittorrentClient(
                settings.qbittorrent_url,
                settings.qbittorrent_username or "",
                settings.qbittorrent_password or "",
            )
            ok = await c.add_url(url)
            await c.close()
        elif manager == "transmission" and settings.transmission_url:
            c = TransmissionClient(
                settings.transmission_url,
                settings.transmission_username or "",
                settings.transmission_password or "",
            )
            ok = await c.add_url(url)
            await c.close()
        label = (title[:60] + "…") if len(title) > 60 else title or url[:60]
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "success" if ok else "warning",
                "message": f"Sent to {manager}: {label}" if ok else "Download submitted",
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": str(e)},
        )


def _format_size(size_bytes: int) -> str:
    """Format bytes into a human-readable string."""
    if not size_bytes:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"
