"""Web routes for Arrmate HTMX interface."""

import asyncio
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

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
from ...auth.plex_sso import (
    build_plex_auth_url,
    clear_plex_state_cookie,
    get_plex_friend_uuids,
    get_plex_state,
    get_plex_user,
    plex_client_id,
    request_pin,
    set_plex_state_cookie,
    validate_pin,
)
from ...auth.rate_limit import login_limiter
from ...auth.session import (
    clear_session_cookie,
    create_session_token,
    set_session_cookie,
)
from ...clients.discovery import discover_services, get_client_for_media_type
from ...config.service_config import save_service_config
from ...clients.lastfm import LastFMClient
from ...clients.lidarr import LidarrClient
from ...clients.openlibrary import OpenLibraryClient
from ...clients.plex import PlexClient
from ...clients.plex_tv import PlexTVClient
from ...clients.radarr import RadarrClient
from ...clients.readmeabook import ReadMeABookClient
from ...clients.sonarr import SonarrClient
from ...clients.tmdb import TMDBClient
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

    # Show default-credentials hint when the admin account still has the factory password
    show_default_creds = False
    try:
        admin = user_db.get_user_by_username("admin")
        if admin and admin.get("must_change_password"):
            show_default_creds = True
    except Exception:
        pass

    from ...config.settings import settings as _settings
    return templates.TemplateResponse(
        "pages/login.html",
        {
            "request": request,
            "next": safe_next_url(next),
            "error": error,
            "show_default_creds": show_default_creds,
            "plex_sso_enabled": _settings.plex_sso_enabled,
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
    allowed, retry_after = await login_limiter.check(login_limiter._get_client_ip(request))
    if not allowed:
        from fastapi.responses import Response as _Response
        return _Response(
            content="Too many login attempts. Please try again later.",
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )

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

    from ...config.settings import settings as _settings
    return templates.TemplateResponse(
        "pages/login.html",
        {
            "request": request,
            "next": safe_next_url(next),
            "error": "Invalid username or password",
            "show_default_creds": False,
            "plex_sso_enabled": _settings.plex_sso_enabled,
        },
        status_code=401,
    )


@auth_router.get("/logout")
async def logout():
    """Log out and redirect to login."""
    response = RedirectResponse(url="/web/login", status_code=303)
    clear_session_cookie(response)
    return response


# ── Plex SSO routes ───────────────────────────────────────────────────────────

@auth_router.get("/auth/plex/start")
async def plex_sso_start(
    request: Request,
    next: str = Query(default="/web/"),
):
    """Initiate Plex SSO login: request a PIN and redirect the user to plex.tv."""
    from ...config.settings import settings as _settings
    if not _settings.plex_sso_enabled:
        return RedirectResponse(url="/web/login", status_code=303)

    # Apply the shared login rate limiter so Plex start counts against the same quota
    allowed, retry_after = await login_limiter.check(login_limiter._get_client_ip(request))
    if not allowed:
        return templates.TemplateResponse(
            "pages/login.html",
            {
                "request": request,
                "next": safe_next_url(next),
                "error": "Too many login attempts. Please try again later.",
                "show_default_creds": False,
                "plex_sso_enabled": True,
            },
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )

    next_url = safe_next_url(next)
    secret_key = auth_manager.get_secret_key()
    client_id = plex_client_id(secret_key)

    try:
        pin_id, pin_code = await request_pin(client_id)
    except Exception:
        logger.exception("Plex PIN request failed")
        return RedirectResponse(
            url="/web/login?error=" + quote_plus("Plex login unavailable. Please try again later."),
            status_code=303,
        )

    # Build the callback URL.  Use ARRMATE_BASE_URL when set (e.g. behind a reverse
    # proxy); otherwise respect X-Forwarded-Proto/Host headers (Traefik, nginx, etc.)
    # so the URL is always https:// even when TLS is terminated at the proxy layer.
    if _settings.arrmate_base_url:
        base = _settings.arrmate_base_url.rstrip("/")
    else:
        proto = request.headers.get("X-Forwarded-Proto") or request.url.scheme
        host = (
            request.headers.get("X-Forwarded-Host")
            or request.headers.get("Host")
            or request.url.netloc
        )
        base = f"{proto}://{host}"
    callback_url = f"{base}/web/auth/plex/callback"
    plex_url = build_plex_auth_url(client_id, pin_code, callback_url)
    logger.info(
        "Plex SSO start: arrmate_base_url=%r base=%r callback_url=%r plex_url=%r",
        _settings.arrmate_base_url, base, callback_url, plex_url,
    )

    response = RedirectResponse(url=plex_url, status_code=302)
    set_plex_state_cookie(response, pin_id, next_url, secret_key)
    return response


@auth_router.get("/auth/plex/callback")
async def plex_sso_callback(request: Request):
    """Handle Plex OAuth callback: validate PIN, resolve identity, create session."""
    from ...config.settings import settings as _settings

    if not _settings.plex_sso_enabled:
        return RedirectResponse(url="/web/login", status_code=303)

    def _login_error(msg: str):
        return RedirectResponse(
            url="/web/login?error=" + quote_plus(msg), status_code=303
        )

    secret_key = auth_manager.get_secret_key()
    client_id = plex_client_id(secret_key)

    # Read + validate the state cookie (signed, max 5 min old — CSRF protection)
    state = get_plex_state(request, secret_key)
    if not state:
        return _login_error("Plex login session expired. Please try again.")
    pin_id, next_url = state

    # Ask Plex whether the user has authorised the PIN
    try:
        auth_token = await validate_pin(pin_id, client_id)
    except Exception:
        logger.exception("Plex PIN validation failed for pin_id=%s", pin_id)
        return _login_error("Plex login unavailable. Please try again later.")

    if not auth_token:
        return _login_error("Plex authorisation was not completed. Please try again.")

    # Fetch the Plex user's identity (UUID, username, email).
    # auth_token is intentionally NOT stored after this block.
    try:
        plex_user = await get_plex_user(auth_token)
    except Exception:
        logger.exception("Failed to fetch Plex user info")
        return _login_error("Could not retrieve Plex account information. Please try again.")
    finally:
        # Ensure auth_token reference is cleared even if get_plex_user raises
        del auth_token

    plex_uuid = plex_user.get("uuid") or plex_user.get("id")
    plex_username = (
        plex_user.get("username") or plex_user.get("title") or "plex_user"
    )
    plex_email = (plex_user.get("email") or "").strip().lower()

    if not plex_uuid:
        return _login_error("Could not verify Plex account identity. Please try again.")

    # Optional email allowlist
    if _settings.plex_sso_allowed_emails:
        allowed_emails = {e.lower().strip() for e in _settings.plex_sso_allowed_emails}
        if plex_email not in allowed_emails:
            logger.warning(
                "Plex SSO: login denied for email=%r (not in allowlist)", plex_email
            )
            return _login_error(
                "Your Plex account is not authorised to access this server."
            )

    # Look up or provision a local user record
    db_user = user_db.get_user_by_plex_id(str(plex_uuid))
    if not db_user:
        role = _settings.plex_sso_default_role

        # Determine whether the new account should start enabled.
        # A user is auto-approved if:
        #   • require_approval is off, OR
        #   • verify_plex_friends is on AND they appear in the server's friends list.
        new_enabled = True
        if _settings.plex_sso_require_approval:
            new_enabled = False
            if _settings.plex_sso_verify_plex_friends and _settings.plex_token:
                try:
                    friend_uuids = await get_plex_friend_uuids(
                        _settings.plex_token, client_id
                    )
                    if str(plex_uuid) in friend_uuids:
                        new_enabled = True
                        logger.info(
                            "Plex SSO: auto-approved %s (Plex friend)", plex_username
                        )
                except Exception:
                    logger.exception("Plex SSO: could not fetch Plex friends list")

        db_user = user_db.create_plex_user(
            plex_id=str(plex_uuid),
            username=plex_username,
            email=plex_email or None,
            role=role,
            enabled=new_enabled,
        )
        if not db_user:
            # Username already taken by a local account — add a suffix and retry once
            db_user = user_db.create_plex_user(
                plex_id=str(plex_uuid),
                username=f"{plex_username}_plex",
                email=plex_email or None,
                role=role,
                enabled=new_enabled,
            )

        # Notify all admins about the new registration
        if db_user:
            admin_ids = user_db.get_admin_and_power_user_ids()
            status_label = "pending approval" if not new_enabled else "auto-approved"
            for admin_id in admin_ids:
                user_db.create_notification(
                    user_id=admin_id,
                    message=(
                        f"New Plex sign-in: '{plex_username}' registered via Plex SSO "
                        f"({status_label}). Enable their account in the Admin Panel."
                        if not new_enabled else
                        f"New Plex sign-in: '{plex_username}' registered and signed in via Plex SSO."
                    ),
                    type="info",
                )

    if not db_user:
        logger.error("Plex SSO: could not create/find user for plex_uuid=%s", plex_uuid)
        return _login_error(
            "Could not create your account. Please contact your administrator."
        )

    if not db_user.get("enabled"):
        return _login_error(
            "Your account is pending admin approval. "
            "Please contact your administrator to enable your access."
        )

    # Issue a normal arrmate session and send the user to their destination
    session_token = create_session_token(
        db_user["id"], db_user["username"], db_user["role"], secret_key
    )
    response = RedirectResponse(url=safe_next_url(next_url), status_code=303)
    set_session_cookie(response, session_token)
    clear_plex_state_cookie(response)
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

    # If setup wizard has never been completed, send admin there now
    if user.get("role") == "admin" and not user_db.is_setup_complete():
        return RedirectResponse(url="/web/setup", status_code=303)

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
    elif len(password) < 8:
        error = "Password must be at least 8 characters"
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


# ===== Setup Wizard =====

_WIZARD_STEPS = [
    ("welcome", "Welcome"),
    ("llm", "AI / LLM"),
    ("media", "Media Services"),
    ("downloads", "Download Clients"),
    ("extras", "Extras"),
    ("done", "Done"),
]


@router.get("/setup", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def setup_wizard(request: Request, step: str = Query(default="welcome")):
    """Setup wizard — shown once after first password change; accessible any time from admin panel."""
    valid_steps = [s[0] for s in _WIZARD_STEPS]
    if step not in valid_steps:
        step = "welcome"

    # Gather current service config for pre-filling form fields
    from ...config.service_config import get_service_config
    current_cfg = get_service_config()

    return templates.TemplateResponse(
        "pages/setup_wizard.html",
        {
            "request": request,
            "step": step,
            "steps": _WIZARD_STEPS,
            "cfg": current_cfg,
            "settings": settings,
            **_base_ctx(request),
        },
    )


@router.post("/setup/skip", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def setup_wizard_skip(request: Request):
    """Mark setup as complete without configuring anything."""
    user_db.mark_setup_complete()
    return RedirectResponse(url="/web/", status_code=303)


@router.post("/setup/save", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def setup_wizard_save(request: Request, next_step: str = Form(default="done")):
    """Save a wizard step's form data and advance to the next step."""
    try:
        form = await request.form()
        # Exclude the next_step control field; save everything else
        service_data = {k: v for k, v in form.multi_items() if k != "next_step"}
        if service_data:
            from ...config.service_config import save_service_config
            save_service_config(service_data)
            reset_parser()
    except Exception as e:
        logger.error("Setup wizard save failed: %s", e)

    if next_step == "done":
        user_db.mark_setup_complete()

    return RedirectResponse(url=f"/web/setup?step={next_step}", status_code=303)


@router.post("/setup/test-service", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def setup_test_service(request: Request):
    """Test a single service connection and return an inline status badge."""
    import httpx as _httpx

    form = await request.form()
    service = str(form.get("service", ""))
    # Accept either a generic "url" field or the service-specific "<service>_url" field.
    # hx-include sends inputs by their actual name attribute (e.g. "sonarr_url"), not "url".
    url = str(form.get("url", "") or form.get(f"{service}_url", ""))
    api_key = str(
        form.get("api_key", "")
        or form.get(f"{service}_api_key", "")
        or form.get(f"{service}_token", "")
    )

    def _badge(ok: bool, msg: str) -> str:
        colour = "green" if ok else "red"
        icon = "✓" if ok else "✗"
        return (
            f'<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium '
            f'bg-{colour}-900/40 text-{colour}-300 border border-{colour}-700/50">'
            f'{icon} {msg}</span>'
        )

    if not url:
        return HTMLResponse(_badge(False, "No URL configured"))

    url = url.rstrip("/")
    try:
        if service == "ollama":
            async with _httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{url}/api/tags")
                return HTMLResponse(_badge(r.status_code < 400, "Connected" if r.status_code < 400 else f"HTTP {r.status_code}"))
        elif service in ("sonarr", "radarr", "lidarr", "readarr", "prowlarr"):
            headers = {"X-Api-Key": api_key} if api_key else {}
            async with _httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{url}/api/v3/system/status", headers=headers)
                return HTMLResponse(_badge(r.status_code == 200, "Connected" if r.status_code == 200 else f"HTTP {r.status_code}"))
        elif service == "plex":
            params = {"X-Plex-Token": api_key} if api_key else {}
            async with _httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{url}/identity", params=params)
                return HTMLResponse(_badge(r.status_code < 400, "Connected" if r.status_code < 400 else f"HTTP {r.status_code}"))
        elif service == "bazarr":
            headers = {"X-Api-Key": api_key} if api_key else {}
            async with _httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{url}/api/system/status", headers=headers)
                return HTMLResponse(_badge(r.status_code == 200, "Connected" if r.status_code == 200 else f"HTTP {r.status_code}"))
        elif service == "sabnzbd":
            async with _httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{url}/api", params={"output": "json", "mode": "version", "apikey": api_key})
                return HTMLResponse(_badge(r.status_code == 200, "Connected" if r.status_code == 200 else f"HTTP {r.status_code}"))
        elif service in ("qbittorrent", "transmission"):
            async with _httpx.AsyncClient(timeout=5) as client:
                r = await client.get(url)
                return HTMLResponse(_badge(r.status_code < 500, "Reachable" if r.status_code < 500 else f"HTTP {r.status_code}"))
        else:
            async with _httpx.AsyncClient(timeout=5) as client:
                r = await client.get(url)
                return HTMLResponse(_badge(r.status_code < 400, "Reachable" if r.status_code < 400 else f"HTTP {r.status_code}"))
    except _httpx.ConnectError:
        return HTMLResponse(_badge(False, "Connection refused"))
    except _httpx.TimeoutException:
        return HTMLResponse(_badge(False, "Timed out"))
    except Exception as e:
        return HTMLResponse(_badge(False, f"Error: {type(e).__name__}"))


@router.post("/setup/reset", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def setup_wizard_reset(request: Request):
    """Reset the setup-complete flag so the wizard can be re-run."""
    from ...auth.user_db import set_app_setting
    set_app_setting("setup_wizard_complete", "0")
    return RedirectResponse(url="/web/setup", status_code=303)


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
    """HTMX partial: notification dropdown panel.

    When accessed directly (no HX-Request header — e.g. after a login
    redirect) we send the user to the main page instead of rendering a bare
    HTML fragment that would appear blank.
    """
    if not request.headers.get("HX-Request"):
        return RedirectResponse(url="/web/", status_code=303)

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
    elif len(password) < 8:
        error = "Password must be at least 8 characters"
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


@router.post("/settings/auth/plex-sso", response_class=HTMLResponse,
             dependencies=[Depends(require_admin)])
async def save_plex_sso_settings(request: Request):
    """Save Plex SSO configuration from the Auth settings panel."""
    from ...config.service_config import save_service_config
    form = await request.form()
    save_service_config({
        "plex_sso_enabled": form.get("plex_sso_enabled", ""),
        "plex_sso_default_role": str(form.get("plex_sso_default_role", "user")),
        "plex_sso_require_approval": form.get("plex_sso_require_approval", ""),
        "plex_sso_verify_plex_friends": form.get("plex_sso_verify_plex_friends", ""),
    })
    return templates.TemplateResponse(
        "partials/auth_settings.html",
        {
            "request": request,
            "settings": settings,
            "auth_success": "Plex SSO settings saved.",
            **_base_ctx(request),
        },
    )


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
    confirmed: str = Form(default=""),
):
    """Execute command and return result HTML with toast.

    mode: optional override — "transcode" to run FFmpeg instead of Sonarr/Radarr search.
    'user' role cannot execute REMOVE or DELETE actions.
    """
    current_user = get_current_user(request)
    user_role = current_user.get("role", "user") if current_user else "user"

    # Outer guard: catches template-rendering failures so HTMX always gets a 200 with
    # visible HTML instead of a silent 500 that leaves the result area blank.
    try:
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

            # Require explicit confirmation for destructive actions (admin/power_user only)
            if enriched.action in _USER_BLOCKED_ACTIONS and confirmed != "true":
                title = enriched.title or "this item"
                if enriched.episodes and enriched.season:
                    ep_str = ", ".join(f"E{e:02d}" for e in sorted(enriched.episodes))
                    delete_description = f"{title} – Season {enriched.season} ({ep_str})"
                elif enriched.season:
                    delete_description = f"{title} – Season {enriched.season}"
                else:
                    delete_description = title
                return templates.TemplateResponse(
                    "partials/delete_confirm.html",
                    {
                        "request": request,
                        "delete_description": delete_description,
                        "command": command,
                        "mode": mode,
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
                    "original_command": command,
                    "show_toast": True,
                    "toast_type": "success" if result.success else "error",
                    "toast_message": result.message,
                },
            )

        except Exception as e:
            logger.exception("Unhandled error in execute_command for %r", command)
            raw = str(e)
            if "400" in raw:
                friendly = "The media service rejected the request (HTTP 400). The item may already exist or have invalid data."
            elif any(c in raw for c in ("401", "403")):
                friendly = "Authentication failed — check your API key in Settings."
            elif any(c in raw for c in ("502", "503", "504")):
                friendly = "A service is temporarily unavailable. Try again in a moment."
            elif any(kw in raw.lower() for kw in ("connection", "connect", "timed out", "timeout")):
                friendly = "Could not reach one of your services. Check that it is running and the URL is correct."
            elif "failed to parse" in raw.lower():
                friendly = "The AI had trouble understanding that request. Try rephrasing it."
            else:
                friendly = f"Something went wrong: {raw}"

            return templates.TemplateResponse(
                "partials/execution_result.html",
                {
                    "request": request,
                    "result": {
                        "success": False,
                        "message": friendly,
                        "errors": [raw],
                    },
                    "original_command": command,
                    "show_toast": True,
                    "toast_type": "error",
                    "toast_message": friendly,
                },
            )

    except Exception as fatal:
        import traceback
        tb = traceback.format_exc()
        logger.exception("Fatal error rendering execute_command response for %r", command)
        safe_tb = tb.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return HTMLResponse(
            content=f"""<div class="card border-red-700/50 p-4">
  <div class="flex gap-3 items-start">
    <span class="text-2xl flex-shrink-0">❌</span>
    <div class="flex-1 min-w-0">
      <p class="text-red-400 font-semibold mb-1">Internal server error</p>
      <p class="text-gray-300 text-sm">An unexpected error occurred while processing your command.</p>
      <details class="mt-3">
        <summary class="text-xs text-gray-500 cursor-pointer hover:text-gray-400 select-none">▶ Show technical details</summary>
        <pre class="mt-2 text-xs text-gray-400 bg-gray-900 p-3 rounded overflow-x-auto whitespace-pre-wrap border border-gray-700/50">{safe_tb}</pre>
      </details>
    </div>
  </div>
</div>""",
            status_code=200,
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

    # Fetch library IDs/titles for cross-referencing (best-effort)
    library_tmdb_ids: set = set()
    library_titles: set = set()
    try:
        if media_type == "tv" and settings.sonarr_url and settings.sonarr_api_key:
            lib_client = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
            try:
                all_series = await lib_client.get_all_series()
                library_tmdb_ids = {s["tmdbId"] for s in all_series if s.get("tmdbId")}
                library_titles = {s["title"].lower() for s in all_series if s.get("title")}
            finally:
                await lib_client.close()
        elif media_type == "movie" and settings.radarr_url and settings.radarr_api_key:
            lib_client = RadarrClient(settings.radarr_url, settings.radarr_api_key)
            try:
                all_movies = await lib_client.get_all_movies()
                library_tmdb_ids = {m["tmdbId"] for m in all_movies if m.get("tmdbId")}
                library_titles = {m["title"].lower() for m in all_movies if m.get("title")}
            finally:
                await lib_client.close()
    except Exception:
        pass  # library check is best-effort; don't block search results

    try:
        client = get_client_for_media_type(media_type)
        try:
            raw_results = await client.search(query)
            for item in raw_results[:20]:
                tmdb_id = item.get("tmdbId")
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
                    "in_library": (
                        (tmdb_id in library_tmdb_ids if tmdb_id else False)
                        or item.get("title", "").lower() in library_titles
                    ),
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
                # Re-search with tvdb: prefix to get full object (seasons, titleSlug, etc.)
                tvdb_id = item.get("tvdbId")
                if tvdb_id:
                    full_lookup = await client.search(f"tvdb:{tvdb_id}")
                    lookup_item = full_lookup[0] if full_lookup else item
                else:
                    lookup_item = item
                await client.add_series_from_lookup(
                    lookup_result=lookup_item,
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
            elif media_type == "music":
                metadata_profiles = await client.get_metadata_profiles()
                metadata_profile_id = metadata_profiles[0]["id"] if metadata_profiles else 1
                await client.add_artist(
                    foreign_artist_id=item["foreignArtistId"],
                    artist_name=item.get("artistName", title),
                    quality_profile_id=profile_id,
                    metadata_profile_id=metadata_profile_id,
                    root_folder_path=root_folder,
                )
            elif media_type in ("audiobook", "book"):
                metadata_profiles = await client.get_metadata_profiles()
                metadata_profile_id = metadata_profiles[0]["id"] if metadata_profiles else 1
                await client.add_author(
                    foreign_author_id=item["foreignAuthorId"],
                    author_name=item.get("authorName", title),
                    quality_profile_id=profile_id,
                    metadata_profile_id=metadata_profile_id,
                    root_folder_path=root_folder,
                )

            added_title = (
                item.get("title") or item.get("artistName") or item.get("authorName") or title
            )
            return templates.TemplateResponse(
                "components/toast.html",
                {
                    "request": request,
                    "type": "success",
                    "message": f"Added '{added_title}' to library",
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
    {"name": "ScanAndAnalyzeFiles", "label": "Scan & Analyze Files", "desc": "Scan all files and run media analysis"},
    {"name": "GenerateIntroVideoMarkers", "label": "Detect Intros", "desc": "Detect intro sequences across all libraries"},
    {"name": "GenerateEndCreditsMarkers", "label": "Detect Credits", "desc": "Detect end-credit sequences (PlexPass)"},
    {"name": "GenerateMediaIndexFiles", "label": "Generate Index Files", "desc": "Generate media index files for faster seeking"},
    {"name": "RecheckPendingIntroVideoMarkers", "label": "Recheck Intro Markers", "desc": "Re-check pending intro detection tasks"},
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


async def _plex_client_for_user(user_id: int) -> PlexClient | None:
    """Return a PlexClient scoped to a home user's token when user_id > 0.

    Calls plex.tv to exchange the admin token for a managed-user token.
    Falls back to the admin token if the switch fails or user_id is 0.
    """
    if not settings.plex_url or not settings.plex_token:
        return None
    if user_id:
        tv = _plex_tv_client()
        if tv:
            try:
                token = await tv.switch_home_user(user_id)
                if token:
                    return PlexClient(settings.plex_url, token)
            except Exception:
                pass
            finally:
                await tv.close()
    return PlexClient(settings.plex_url, settings.plex_token)


def _plex_thumb_url(path: str) -> str:
    """Build a proxied Plex thumbnail URL (keeps token server-side)."""
    import urllib.parse
    return f"/web/plex/thumb?path={urllib.parse.quote(path, safe='')}"


@router.get("/upcoming", response_class=HTMLResponse)
async def upcoming_page(request: Request):
    """Upcoming calendar page — episodes and movies airing in the next few days."""
    return templates.TemplateResponse(
        "pages/upcoming.html",
        {"request": request, **_base_ctx(request)},
    )


@router.get("/upcoming/content", response_class=HTMLResponse)
async def upcoming_content(
    request: Request,
    days: int = Query(default=7, ge=1, le=30),
):
    """HTMX partial: combined Sonarr + Radarr calendar for the next N days."""
    from datetime import date, datetime, timedelta
    from itertools import groupby as _groupby
    from zoneinfo import ZoneInfo

    _eastern = ZoneInfo("America/New_York")

    def _parse_air_time(air_date_utc_str: str) -> str | None:
        """Convert an airDateUtc string to a human-readable Eastern time string."""
        if not air_date_utc_str:
            return None
        try:
            dt_utc = datetime.fromisoformat(air_date_utc_str.replace("Z", "+00:00"))
            # Sonarr uses midnight UTC as a placeholder when the air time is unknown
            if dt_utc.hour == 0 and dt_utc.minute == 0:
                return None
            dt_east = dt_utc.astimezone(_eastern)
            h = dt_east.hour % 12 or 12
            ampm = "AM" if dt_east.hour < 12 else "PM"
            tz_abbr = "EDT" if dt_east.dst() else "EST"
            return f"{h}:{dt_east.minute:02d} {ampm} {tz_abbr}"
        except Exception:
            return None

    today = date.today()
    start_str = today.isoformat()
    end_str = (today + timedelta(days=days)).isoformat()

    events: list = []
    error = None

    # --- Sonarr ---
    if settings.sonarr_url and settings.sonarr_api_key:
        try:
            sonarr = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
            eps = await sonarr.get_calendar(start_str, end_str, include_series=True)
            await sonarr.close()
            for ep in eps:
                series = ep.get("series") or {}
                air_date = ep.get("airDate") or (ep.get("airDateUtc") or "")[:10]
                if not air_date:
                    continue
                poster = None
                for img in (series.get("images") or []):
                    if img.get("coverType") == "poster":
                        url = img.get("remoteUrl") or img.get("url", "")
                        poster = url if url.startswith("http") else None
                        break
                events.append({
                    "kind": "tv",
                    "date": air_date,
                    "show": series.get("title", ""),
                    "episode_label": f"S{ep.get('seasonNumber', 0):02d}E{ep.get('episodeNumber', 0):02d}",
                    "title": ep.get("title", ""),
                    "network": series.get("network", ""),
                    "has_file": bool(ep.get("hasFile")),
                    "monitored": bool(ep.get("monitored")),
                    "poster": poster,
                    "air_time_est": _parse_air_time(ep.get("airDateUtc", "")),
                })
        except Exception as e:
            error = str(e)

    # --- Radarr ---
    if settings.radarr_url and settings.radarr_api_key:
        try:
            radarr = RadarrClient(settings.radarr_url, settings.radarr_api_key)
            movies = await radarr.get_calendar(start_str, end_str)
            await radarr.close()
            for m in movies:
                release_date = None
                for field in ("inCinemas", "digitalRelease", "physicalRelease"):
                    val = (m.get(field) or "")[:10]
                    if val and start_str <= val <= end_str:
                        release_date = val
                        break
                if not release_date:
                    release_date = (
                        m.get("inCinemas") or m.get("digitalRelease") or m.get("physicalRelease") or ""
                    )[:10]
                if not release_date:
                    continue
                poster = None
                for img in (m.get("images") or []):
                    if img.get("coverType") == "poster":
                        url = img.get("remoteUrl") or img.get("url", "")
                        poster = url if url.startswith("http") else None
                        break
                release_type = (
                    "Cinema" if (m.get("inCinemas") or "")[:10] == release_date
                    else "Digital" if (m.get("digitalRelease") or "")[:10] == release_date
                    else "Physical"
                )
                events.append({
                    "kind": "movie",
                    "date": release_date,
                    "show": "",
                    "episode_label": "",
                    "title": m.get("title", ""),
                    "network": release_type,
                    "has_file": bool(m.get("hasFile")),
                    "monitored": bool(m.get("monitored")),
                    "poster": poster,
                    "year": m.get("year"),
                    "air_time_est": None,
                })
        except Exception as ex:
            if not error:
                error = str(ex)

    events.sort(key=lambda e: (e["date"], e.get("show") or e["title"]))
    grouped = [
        {"date": d, "events": list(evs)}
        for d, evs in _groupby(events, key=lambda e: e["date"])
    ]

    return templates.TemplateResponse(
        "partials/upcoming_content.html",
        {
            "request": request,
            "grouped": grouped,
            "days": days,
            "error": error,
            "total": len(events),
        },
    )


@router.get("/plex", response_class=HTMLResponse)
async def plex_page(request: Request):
    """Plex hub page."""
    plex = _plex_client()
    configured = plex is not None
    accounts = []
    home_users = []
    if plex:
        try:
            raw_accounts = await plex.get_accounts()
            # Normalize: Plex returns `name` on /accounts but `title` on User objects in history
            accounts = [
                {
                    "id": a.get("id"),
                    "title": (
                        a.get("title") or a.get("name")
                        or ("Main User" if a.get("id") == 1 else f"User {a.get('id', '')}")
                    ),
                }
                for a in raw_accounts
                if a.get("id") not in (None, 0)  # exclude system account 0
            ]
        except Exception:
            pass
        finally:
            await plex.close()
    # Load home users from plex.tv for the user switcher (managed users only)
    tv = _plex_tv_client()
    if tv:
        try:
            raw_users = await tv.get_home_users()
            home_users = [
                {
                    "id": u.get("id"),
                    "title": u.get("title") or u.get("name") or f"User {u.get('id', '')}",
                    "thumb": u.get("thumb"),
                }
                for u in raw_users
                if u.get("id") is not None and not u.get("admin", False)
            ]
        except Exception:
            pass
        finally:
            await tv.close()

    # For regular users: find their Plex accountID so we can lock history to them.
    # Match by username — the username stored in our DB matches the Plex account name.
    current_user = get_current_user(request)
    viewer_account_id: int | None = None
    if current_user and current_user.get("role") == "user":
        username_lower = (current_user.get("username") or "").lower()
        for acct in accounts:
            if (acct.get("title") or "").lower() == username_lower:
                viewer_account_id = acct["id"]
                break

    return templates.TemplateResponse(
        "pages/plex.html",
        {
            "request": request,
            **_base_ctx(request),
            "configured": configured,
            "accounts": accounts,
            "home_users": home_users,
            "butler_tasks": BUTLER_TASKS,
            "viewer_account_id": viewer_account_id,
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

    # Regular users can only see their own history — enforce server-side.
    current_user = get_current_user(request)
    if current_user and current_user.get("role") == "user":
        account_id = 0  # will be overridden below after accounts are fetched

    items = []
    error = None
    plex = _plex_client()
    if plex:
        try:
            # Build account_id → display name map so history rows show real usernames.
            # Account ID 1 is always the server owner; Plex may return it with no title.
            raw_accounts = await plex.get_accounts()
            account_name_map: dict[int, str] = {}
            for acct in raw_accounts:
                acct_id = acct.get("id", 0)
                acct_name = acct.get("title") or acct.get("name") or ""
                if acct_id == 1 and not acct_name:
                    acct_name = "Main User"
                if acct_name:
                    account_name_map[acct_id] = acct_name
            # Ensure account 1 always has a label
            account_name_map.setdefault(1, "Main User")

            # For regular users, lock history to their own Plex account.
            if current_user and current_user.get("role") == "user":
                username_lower = (current_user.get("username") or "").lower()
                for acct_id, acct_name in account_name_map.items():
                    if acct_name.lower() == username_lower:
                        account_id = acct_id
                        break
                # If no match found, use a sentinel that will return no results
                if account_id == 0:
                    account_id = -1

            raw = await plex.get_history(
                account_id=account_id if account_id > 0 else None,
                limit=fetch_limit,
                min_date=cutoff if cutoff else None,
            )
            for item in raw:
                viewed_at = item.get("viewedAt", 0)
                # Skip items with no timestamp
                if viewed_at == 0:
                    continue
                # Secondary client-side guard (server already filters but be safe)
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
                # History items expose accountID as a plain int field, not a nested dict.
                item_account_id = item.get("accountID") or 0
                user_name = account_name_map.get(item_account_id, "")
                items.append({
                    "title": title,
                    "subtitle": subtitle,
                    "type": media_type,
                    "viewed_at": viewed_at,
                    "thumb": thumb,
                    "rating_key": item.get("ratingKey"),
                    "user": user_name,
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
async def plex_continue_watching(
    request: Request,
    user_id: int = Query(default=0),
):
    """HTMX partial: continue watching list."""
    items = []
    error = None
    plex = await _plex_client_for_user(user_id)
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
async def plex_on_deck(
    request: Request,
    user_id: int = Query(default=0),
):
    """HTMX partial: on deck items."""
    items = []
    error = None
    plex = await _plex_client_for_user(user_id)
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


@router.get("/plex/bytitle", response_class=HTMLResponse)
async def plex_by_title(
    request: Request,
    bt_search: str = Query(default=""),
    bt_letter: str = Query(default=""),
    bt_media_type: str = Query(default="all"),
):
    """HTMX partial: watch history grouped and sorted by title (served from local cache)."""
    from ...cache import plex_cache

    error = None
    last_synced = None

    # Seed the cache on first load (if empty or stale)
    if plex_cache.is_stale():
        plex = _plex_client()
        if plex:
            try:
                raw = await plex.get_history(limit=5000)
                plex_cache.populate_cache(raw)
            except Exception as e:
                error = str(e)
            finally:
                await plex.close()
        else:
            error = "Plex is not configured"

    last_synced = plex_cache.get_last_synced()
    cached = plex_cache.get_cached_history()

    groups: dict = {}
    for item in cached:
        media_type_str = item.get("type", "")
        kind = "tv" if media_type_str in ("episode", "season") else "movie"

        if bt_media_type == "tv" and kind != "tv":
            continue
        if bt_media_type == "movie" and kind != "movie":
            continue

        if kind == "tv":
            group_title = item.get("grandparent_title") or item.get("title") or ""
            thumb = item.get("grandparent_thumb") or item.get("thumb")
        else:
            group_title = item.get("title") or ""
            thumb = item.get("thumb")

        if not group_title:
            continue

        # Letter filter
        sort_title = group_title
        for prefix in ("The ", "A ", "An "):
            if sort_title.startswith(prefix):
                sort_title = sort_title[len(prefix):]
                break
        first = sort_title[0].upper() if sort_title else "?"
        if bt_letter == "#":
            if first.isalpha():
                continue
        elif bt_letter:
            if first != bt_letter:
                continue

        if bt_search and bt_search.lower() not in group_title.lower():
            continue

        if group_title not in groups:
            groups[group_title] = {
                "title": group_title,
                "kind": kind,
                "thumb": _plex_thumb_url(thumb) if thumb else None,
                "count": 0,
                "last_watched": 0,
                "unique_accounts": set(),
            }
        groups[group_title]["count"] += 1
        viewed_at = item.get("viewed_at") or 0
        if viewed_at > groups[group_title]["last_watched"]:
            groups[group_title]["last_watched"] = viewed_at
        acct = item.get("account_id")
        if acct:
            groups[group_title]["unique_accounts"].add(acct)

    # Convert sets to counts for template
    for g in groups.values():
        g["user_count"] = len(g.pop("unique_accounts"))

    sorted_groups = sorted(groups.values(), key=lambda g: g["title"].lower())
    return templates.TemplateResponse(
        "partials/plex_bytitle.html",
        {
            "request": request,
            "groups": sorted_groups,
            "error": error,
            "search": bt_search,
            "letter": bt_letter,
            "media_type": bt_media_type,
            "last_synced": last_synced,
            "total_cached": len(cached),
        },
    )


@router.post("/plex/bytitle/sync", response_class=HTMLResponse)
async def plex_bytitle_sync(request: Request):
    """Force-refresh the Plex history cache and return updated content."""
    from ...cache import plex_cache

    plex = _plex_client()
    if not plex:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": "Plex is not configured"},
        )
    try:
        raw = await plex.get_history(limit=5000)
        count = plex_cache.populate_cache(raw)
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "success",
                "message": f"History synced — {count} items cached",
            },
            headers={"HX-Trigger": "plexBytitleSynced"},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": f"Sync failed: {e}"},
        )
    finally:
        await plex.close()


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


@router.delete("/plex/session/{session_id}", response_class=HTMLResponse)
async def terminate_plex_session(
    request: Request,
    session_id: str,
    reason: str = Query(default="Session terminated by Arrmate"),
):
    """Terminate an active Plex streaming session (session_id = Session.id UUID)."""
    plex = _plex_client()
    if not plex:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": "Plex is not configured"},
        )
    try:
        ok = await plex.terminate_session(session_id, reason)
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


@router.post("/plex/watched/{rating_key}", response_class=HTMLResponse)
async def plex_mark_watched(request: Request, rating_key: str):
    """Mark a Plex item as watched."""
    plex = _plex_client()
    if not plex:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": "Plex is not configured"},
        )
    try:
        ok = await plex.mark_watched(rating_key)
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "success" if ok else "error",
                "message": "Marked as watched" if ok else "Failed to mark as watched",
            },
        )
    finally:
        await plex.close()


@router.post("/plex/unwatched/{rating_key}", response_class=HTMLResponse)
async def plex_mark_unwatched(request: Request, rating_key: str):
    """Mark a Plex item as unwatched."""
    plex = _plex_client()
    if not plex:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": "Plex is not configured"},
        )
    try:
        ok = await plex.mark_unwatched(rating_key)
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "success" if ok else "error",
                "message": "Marked as unwatched" if ok else "Failed to mark as unwatched",
            },
        )
    finally:
        await plex.close()


@router.get("/plex/playlists", response_class=HTMLResponse)
async def plex_playlists(request: Request):
    """HTMX partial: playlist list."""
    playlists = []
    error = None
    plex = _plex_client()
    if plex:
        try:
            raw = await plex.get_playlists()
            for pl in raw:
                duration_ms = pl.get("duration", 0) or 0
                duration_h = duration_ms // 3_600_000
                duration_m = (duration_ms % 3_600_000) // 60_000
                duration_str = (
                    f"{duration_h}h {duration_m}m" if duration_h else f"{duration_m}m"
                ) if duration_ms else ""
                thumb_path = pl.get("thumb") or pl.get("composite")
                playlists.append({
                    "id": pl.get("ratingKey"),
                    "title": pl.get("title", "Untitled"),
                    "playlist_type": pl.get("playlistType", "video"),
                    "item_count": pl.get("leafCount", 0),
                    "duration": duration_str,
                    "thumb": _plex_thumb_url(thumb_path) if thumb_path else None,
                    "summary": pl.get("summary", ""),
                })
        except Exception as e:
            error = str(e)
        finally:
            await plex.close()
    else:
        error = "Plex is not configured"
    return templates.TemplateResponse(
        "partials/plex_playlists.html",
        {"request": request, "playlists": playlists, "error": error},
    )


@router.get("/plex/sessions", response_class=HTMLResponse)
async def plex_sessions_panel(request: Request):
    """HTMX partial: active streaming sessions with transcode/bandwidth detail."""
    sessions = []
    error = None
    plex = _plex_client()
    if plex:
        try:
            raw = await plex.get_sessions()
            for s in raw:
                media_type = s.get("type", "")
                if media_type == "episode":
                    title = s.get("grandparentTitle", "")
                    subtitle = (
                        f"S{s.get('parentIndex', 0):02d}E{s.get('index', 0):02d}"
                        f" — {s.get('title', '')}"
                    )
                else:
                    title = s.get("title", "Unknown")
                    subtitle = str(s.get("year", "")) if s.get("year") else ""
                duration = s.get("duration", 0)
                offset = s.get("viewOffset", 0)
                pct = int(offset / duration * 100) if duration else 0
                # Transcode info
                tc = s.get("TranscodeSession") or {}
                video_decision = tc.get("videoDecision", "directplay")
                audio_decision = tc.get("audioDecision", "directplay")
                # Source codec
                media_list = s.get("Media") or [{}]
                src = media_list[0] if media_list else {}
                src_video = src.get("videoCodec", "")
                src_audio = src.get("audioCodec", "")
                src_res = f"{src.get('width', '')}×{src.get('height', '')}" if src.get("width") else ""
                # Bandwidth
                bandwidth = s.get("Session", {}).get("bandwidth", 0) or 0
                bw_str = f"{bandwidth // 1000} Mbps" if bandwidth >= 1000 else (f"{bandwidth} Kbps" if bandwidth else "")
                sessions.append({
                    "title": title,
                    "subtitle": subtitle,
                    "type": media_type,
                    "pct": pct,
                    "user": s.get("User", {}).get("title", ""),
                    "user_thumb": s.get("User", {}).get("thumb", ""),
                    "player": s.get("Player", {}).get("title", ""),
                    "platform": s.get("Player", {}).get("platform", ""),
                    "state": s.get("Player", {}).get("state", "playing"),
                    "location": s.get("Session", {}).get("location", ""),
                    "bandwidth": bw_str,
                    "video_decision": video_decision,
                    "audio_decision": audio_decision,
                    "src_video": src_video,
                    "src_audio": src_audio,
                    "src_res": src_res,
                    "dst_video": tc.get("videoCodec", src_video),
                    "dst_audio": tc.get("audioCodec", src_audio),
                    "session_id": s.get("Session", {}).get("id", ""),
                    "thumb": _plex_thumb_url(s.get("thumb") or s.get("grandparentThumb", "")) if (s.get("thumb") or s.get("grandparentThumb")) else None,
                })
        except Exception as e:
            error = str(e)
        finally:
            await plex.close()
    else:
        error = "Plex is not configured"
    return templates.TemplateResponse(
        "partials/plex_sessions.html",
        {"request": request, "sessions": sessions, "error": error},
    )


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
                    # Session.id is the UUID required by DELETE /status/sessions/terminate
                    "session_id": s.get("Session", {}).get("id", ""),
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


# ── API Token Management ──────────────────────────────────────────────────────

@router.get("/api-tokens", response_class=HTMLResponse)
async def api_tokens_page(request: Request):
    """API token management page — shows the current user's tokens."""
    user = get_current_user(request)
    if not user:
        raise AuthRedirectException("/web/login?next=/web/api-tokens")
    tokens = user_db.list_api_tokens(user["user_id"])
    return templates.TemplateResponse(
        "pages/api_tokens.html",
        {"request": request, "tokens": tokens, "new_token": None, **_base_ctx(request)},  # nosec B105
    )


@router.post("/api-tokens/create", response_class=HTMLResponse)
async def api_tokens_create(
    request: Request,
    name: str = Form(...),
    expires_days: str = Form(default=""),
):
    """Create a new API token for the current user."""
    user = get_current_user(request)
    if not user:
        raise AuthRedirectException("/web/login")

    exp_days = None
    if expires_days.strip():
        try:
            exp_days = int(expires_days.strip())
            if exp_days <= 0:
                exp_days = None
        except ValueError:
            exp_days = None

    _name = name.strip() or "API Token"
    _token_id, plain_token = user_db.create_api_token(
        user_id=user["user_id"],
        name=_name,
        expires_days=exp_days,
    )
    tokens = user_db.list_api_tokens(user["user_id"])
    return templates.TemplateResponse(
        "pages/api_tokens.html",
        {
            "request": request,
            "tokens": tokens,
            "new_token": plain_token,
            "new_token_name": _name,
            **_base_ctx(request),
        },
    )


@router.delete("/api-tokens/{token_id}", response_class=HTMLResponse)
async def api_tokens_delete(request: Request, token_id: str):
    """Delete one of the current user's tokens."""
    user = get_current_user(request)
    if not user:
        raise AuthRedirectException("/web/login")
    user_db.delete_api_token(token_id, user["user_id"])
    tokens = user_db.list_api_tokens(user["user_id"])
    return templates.TemplateResponse(
        "partials/api_tokens_list.html",
        {"request": request, "tokens": tokens, **_base_ctx(request)},
    )


# ── Discover (TMDB) ──────────────────────────────────────────────────────────

_DISCOVER_CATEGORIES = {
    "trending_movies":  ("trending movies", "movie"),
    "trending_tv":      ("trending TV shows", "tv"),
    "upcoming":         ("upcoming movies", "movie"),
    "now_playing":      ("movies in theatres", "movie"),
    "on_the_air":       ("TV shows on the air", "tv"),
    "popular_movies":   ("popular movies", "movie"),
    "popular_tv":       ("popular TV shows", "tv"),
    "top_rated_movies": ("top rated movies", "movie"),
    "top_rated_tv":     ("top rated TV shows", "tv"),
    # Music (Last.fm)
    "top_artists":      ("top artists", "music"),
    "top_tracks":       ("top tracks", "music"),
    # Books (Open Library)
    "books_trending":   ("trending books", "book"),
    "books_weekly":     ("trending this week", "book"),
    "books_fiction":    ("fiction", "book"),
    "books_mystery":    ("mystery & thriller", "book"),
    "books_scifi":      ("science fiction", "book"),
    # Audiobooks (ReadMeABook)
    "audiobooks_popular":  ("popular audiobooks", "audiobook"),
    "audiobooks_new":      ("new audiobook releases", "audiobook"),
}

_MUSIC_CATEGORIES = {"top_artists", "top_tracks"}
_BOOK_CATEGORIES = {"books_trending", "books_weekly", "books_fiction", "books_mystery", "books_scifi"}
_AUDIOBOOK_CATEGORIES = {"audiobooks_popular", "audiobooks_new"}


def _tmdb_client() -> TMDBClient | None:
    if settings.tmdb_api_key:
        return TMDBClient(settings.tmdb_api_key)
    return None


def _lastfm_client() -> LastFMClient | None:
    if settings.lastfm_api_key:
        return LastFMClient(settings.lastfm_api_key)
    return None


@router.get("/discover", response_class=HTMLResponse)
async def discover_page(request: Request):
    return templates.TemplateResponse(
        "pages/discover.html",
        {
            "request": request,
            "tmdb_ok":        bool(settings.tmdb_api_key),
            "lastfm_ok":      bool(settings.lastfm_api_key),
            "sonarr_ok":      bool(settings.sonarr_url and settings.sonarr_api_key),
            "radarr_ok":      bool(settings.radarr_url and settings.radarr_api_key),
            "lidarr_ok":      bool(settings.lidarr_url and settings.lidarr_api_key),
            "readmeabook_ok": bool(settings.readmeabook_url and settings.readmeabook_api_key),
            "readarr_ok":     bool(settings.readarr_url and settings.readarr_api_key),
            # Open Library needs no key — always available
            "openlibrary_ok": True,
            **_base_ctx(request),
        },
    )


@router.get("/discover/results", response_class=HTMLResponse)
async def discover_results(
    request: Request,
    category: str = Query(default="trending_movies"),
):
    media_type = _DISCOVER_CATEGORIES.get(category, ("", "movie"))[1]
    items: list = []
    source = "tmdb"
    error = None

    try:
        # ── Music (Last.fm) ───────────────────────────────────────────────────
        if category in _MUSIC_CATEGORIES:
            source = "lastfm"
            lfm = _lastfm_client()
            if not lfm:
                error = "LASTFM_API_KEY is not configured."
            else:
                try:
                    if category == "top_artists":
                        items = await lfm.get_top_artists()
                    else:
                        items = await lfm.get_top_tracks()
                finally:
                    await lfm.close()

            # Cross-reference Lidarr library by artist name
            library_names: set[str] = set()
            if settings.lidarr_url and settings.lidarr_api_key:
                try:
                    lidarr = LidarrClient(settings.lidarr_url, settings.lidarr_api_key)
                    all_artists = await lidarr.get_all_artists()
                    await lidarr.close()
                    library_names = {
                        a.get("artistName", "").lower() for a in all_artists if a.get("artistName")
                    }
                except Exception:
                    pass
            for item in items:
                item["in_library"] = item.get("display_title", "").lower() in library_names

        # ── Books (Open Library) ──────────────────────────────────────────────
        elif category in _BOOK_CATEGORIES:
            source = "openlibrary"
            ol = OpenLibraryClient()
            try:
                if category == "books_trending":
                    items = await ol.get_trending_daily()
                elif category == "books_weekly":
                    items = await ol.get_trending_weekly()
                elif category == "books_fiction":
                    items = await ol.get_subject("fiction")
                elif category == "books_mystery":
                    items = await ol.get_subject("mystery")
                elif category == "books_scifi":
                    items = await ol.get_subject("science_fiction")
            finally:
                await ol.close()

            # Cross-reference Readarr library by title
            library_names = set()
            if settings.readarr_url and settings.readarr_api_key:
                try:
                    from ...clients.readarr import ReadarrClient
                    readarr = ReadarrClient(settings.readarr_url, settings.readarr_api_key)
                    all_authors = await readarr.get_all_authors()
                    await readarr.close()
                    library_names = {
                        a.get("authorName", "").lower() for a in all_authors if a.get("authorName")
                    }
                except Exception:
                    pass
            for item in items:
                item["in_library"] = item.get("author", "").lower() in library_names

        # ── Audiobooks (ReadMeABook) ───────────────────────────────────────────
        elif category in _AUDIOBOOK_CATEGORIES:
            source = "readmeabook"
            if not (settings.readmeabook_url and settings.readmeabook_api_key):
                error = "ReadMeABook is not configured."
            else:
                rmab = ReadMeABookClient(settings.readmeabook_url, settings.readmeabook_api_key)
                try:
                    if category == "audiobooks_popular":
                        raw = await rmab.get_popular()
                    else:
                        raw = await rmab.get_new_releases()

                    # Normalise to common card schema
                    existing_asins: set[str] = set()
                    try:
                        reqs = await rmab.get_requests()
                        existing_asins = {r.get("asin", "") for r in reqs if r.get("asin")}
                    except Exception:
                        pass

                    for b in raw:
                        title = b.get("title") or b.get("name", "Unknown")
                        asin = b.get("asin", "")
                        items.append({
                            "display_title": title,
                            "author": b.get("author", ""),
                            "year": "",
                            "poster": b.get("image") or b.get("cover") or b.get("coverUrl"),
                            "overview": b.get("description", ""),
                            "asin": asin,
                            "media_type": "audiobook",
                            "in_library": asin in existing_asins,
                        })
                finally:
                    await rmab.close()

        # ── Movies / TV (TMDB) ────────────────────────────────────────────────
        else:
            source = "tmdb"
            tmdb = _tmdb_client()
            if not tmdb:
                error = "TMDB_API_KEY is not configured."
            else:
                try:
                    if category == "trending_movies":
                        items = await tmdb.get_trending_movies()
                    elif category == "trending_tv":
                        items = await tmdb.get_trending_tv()
                    elif category == "upcoming":
                        items = await tmdb.get_upcoming_movies()
                    elif category == "now_playing":
                        items = await tmdb.get_now_playing()
                    elif category == "on_the_air":
                        items = await tmdb.get_tv_on_the_air()
                    elif category == "popular_movies":
                        items = await tmdb.get_popular_movies()
                    elif category == "popular_tv":
                        items = await tmdb.get_popular_tv()
                    elif category == "top_rated_movies":
                        items = await tmdb.get_top_rated_movies()
                    elif category == "top_rated_tv":
                        items = await tmdb.get_top_rated_tv()
                    else:
                        items = await tmdb.get_trending_movies()

                    for item in items:
                        item["poster"] = tmdb.poster_url(item.get("poster_path"), "w342")
                        raw = item.get("release_date") or item.get("first_air_date") or ""
                        item["year"] = raw[:4] if raw else ""
                        item["display_title"] = item.get("title") or item.get("name") or "Unknown"
                        item["rating"] = round(item.get("vote_average", 0), 1)
                        item["media_type"] = media_type

                    # Cross-reference library
                    library_tmdb_ids: set[int] = set()
                    library_titles: set[str] = set()
                    if media_type == "movie" and settings.radarr_url and settings.radarr_api_key:
                        try:
                            radarr = RadarrClient(settings.radarr_url, settings.radarr_api_key)
                            all_movies = await radarr.get_all_movies()
                            await radarr.close()
                            library_tmdb_ids = {m["tmdbId"] for m in all_movies if m.get("tmdbId")}
                        except Exception:
                            pass
                    elif media_type == "tv" and settings.sonarr_url and settings.sonarr_api_key:
                        try:
                            sonarr_lib = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
                            all_series = await sonarr_lib.get_all_series()
                            await sonarr_lib.close()
                            library_tmdb_ids = {s["tmdbId"] for s in all_series if s.get("tmdbId")}
                            library_titles = {
                                s["title"].lower() for s in all_series if s.get("title")
                            }
                        except Exception:
                            pass
                    for item in items:
                        by_id = item.get("id") in library_tmdb_ids
                        by_title = item.get("display_title", "").lower() in library_titles
                        item["in_library"] = by_id or by_title
                finally:
                    await tmdb.close()

    except Exception as e:
        logger.error("Discover error (category=%s): %s", category, e)
        error = str(e)
        items = []

    return templates.TemplateResponse(
        "partials/discover_results.html",
        {
            "request": request,
            "items": items,
            "media_type": media_type,
            "source": source,
            "error": error,
            "sonarr_ok":      bool(settings.sonarr_url and settings.sonarr_api_key),
            "radarr_ok":      bool(settings.radarr_url and settings.radarr_api_key),
            "lidarr_ok":      bool(settings.lidarr_url and settings.lidarr_api_key),
            "readmeabook_ok": bool(settings.readmeabook_url and settings.readmeabook_api_key),
            "readarr_ok":     bool(settings.readarr_url and settings.readarr_api_key),
            **_base_ctx(request),
        },
    )


@router.post("/discover/add", response_class=HTMLResponse)
async def discover_add(
    request: Request,
    media_type: str = Form(...),
    tmdb_id: int = Form(...),
    title: str = Form(...),
    _: None = Depends(require_power_user),
):
    """Add a discovered title to Radarr (movies) or Sonarr (TV)."""
    try:
        if media_type == "movie":
            if not (settings.radarr_url and settings.radarr_api_key):
                raise ValueError("Radarr is not configured")
            radarr = RadarrClient(settings.radarr_url, settings.radarr_api_key)
            profiles = await radarr.get_quality_profiles()
            root_folders = await radarr.get_root_folders()
            if not profiles or not root_folders:
                raise ValueError("Radarr has no quality profiles or root folders configured")
            added = await radarr.add_movie(
                tmdb_id=tmdb_id,
                title=title,
                quality_profile_id=profiles[0]["id"],
                root_folder_path=root_folders[0]["path"],
            )
            await radarr.close()
            msg = f"Added '{added.get('title', title)}' to Radarr"
            success = True

        elif media_type == "tv":
            if not (settings.sonarr_url and settings.sonarr_api_key):
                raise ValueError("Sonarr is not configured")
            # Get TVDB ID from TMDB
            tmdb = _tmdb_client()
            if not tmdb:
                raise ValueError("TMDB API key not configured")
            ext = await tmdb.get_external_ids(tmdb_id, "tv")
            await tmdb.close()
            tvdb_id = ext.get("tvdb_id")
            if not tvdb_id:
                raise ValueError(f"Could not find TVDB ID for '{title}' — it may not be in TVDB yet")

            sonarr = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
            profiles = await sonarr.get_quality_profiles()
            root_folders = await sonarr.get_root_folders()
            if not profiles or not root_folders:
                raise ValueError("Sonarr has no quality profiles or root folders configured")
            # Lookup via tvdb: to get the full series object (titleSlug, seasons, etc.)
            lookup = await sonarr.search(f"tvdb:{tvdb_id}")
            if not lookup:
                raise ValueError(
                    f"Could not find '{title}' in Sonarr's database (TVDB:{tvdb_id})"
                )
            # Pass the full lookup result so all Sonarr-required fields are present
            added = await sonarr.add_series_from_lookup(
                lookup_result=lookup[0],
                quality_profile_id=profiles[0]["id"],
                root_folder_path=root_folders[0]["path"],
            )
            await sonarr.close()
            msg = f"Added '{added.get('title', title)}' to Sonarr"
            success = True

        else:
            raise ValueError(f"Unknown media type: {media_type}")

    except Exception as e:
        # Try to extract the actual error message from the HTTP response body
        # (Sonarr/Radarr return JSON arrays like [{"errorMessage": "..."}] on 400)
        detail = str(e)
        if hasattr(e, "response"):
            try:
                body = e.response.json()
                if isinstance(body, list) and body:
                    detail = body[0].get("errorMessage") or body[0].get("message") or detail
                elif isinstance(body, dict):
                    detail = body.get("message") or body.get("errorMessage") or detail
            except Exception:
                pass
        if "already" in detail.lower() or "exists" in detail.lower():
            msg = f"'{title}' is already in your library"
            success = True
        else:
            msg = detail
            success = False

    return templates.TemplateResponse(
        "partials/discover_add_btn.html",
        {
            "request": request,
            "success": success,
            "message": msg,
            "media_type": media_type,
            "tmdb_id": tmdb_id,
            "title": title,
        },
    )


@router.post("/discover/request", response_class=HTMLResponse)
async def discover_request(
    request: Request,
    asin: str = Form(...),
    title: str = Form(...),
    author: str = Form(default=""),
):
    """Submit an audiobook request to ReadMeABook."""
    if not (settings.readmeabook_url and settings.readmeabook_api_key):
        return templates.TemplateResponse(
            "partials/discover_add_btn.html",
            {"request": request, "success": False,
             "message": "ReadMeABook is not configured", "media_type": "audiobook"},
        )
    rmab = ReadMeABookClient(settings.readmeabook_url, settings.readmeabook_api_key)
    try:
        # Check for duplicate before submitting
        existing = await rmab.get_requests()
        already = any(
            r.get("asin") == asin or r.get("title", "").lower() == title.lower()
            for r in existing
        )
        if already:
            return templates.TemplateResponse(
                "partials/discover_add_btn.html",
                {"request": request, "success": True,
                 "message": f"'{title}' is already requested", "media_type": "audiobook"},
            )
        await rmab.create_request(asin=asin, title=title, author=author)
        return templates.TemplateResponse(
            "partials/discover_add_btn.html",
            {"request": request, "success": True,
             "message": f"Requested '{title}'", "media_type": "audiobook"},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "partials/discover_add_btn.html",
            {"request": request, "success": False,
             "message": str(e), "media_type": "audiobook"},
        )
    finally:
        await rmab.close()


# ===== Tags Management =====


@router.get("/tags", response_class=HTMLResponse, dependencies=[Depends(require_power_user)])
async def tags_page(request: Request):
    """Tag management page for Sonarr and Radarr."""
    sonarr_configured = bool(settings.sonarr_url and settings.sonarr_api_key)
    radarr_configured = bool(settings.radarr_url and settings.radarr_api_key)
    return templates.TemplateResponse(
        "pages/tags.html",
        {
            "request": request,
            **_base_ctx(request),
            "sonarr_configured": sonarr_configured,
            "radarr_configured": radarr_configured,
        },
    )


@router.get("/tags/list", response_class=HTMLResponse, dependencies=[Depends(require_power_user)])
async def tags_list(
    request: Request,
    service: str = Query(default="radarr"),
):
    """HTMX partial: list tags for a service with item counts."""
    tags = []
    error = None
    try:
        if service == "sonarr" and settings.sonarr_url and settings.sonarr_api_key:
            client = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
            try:
                raw_tags = await client.get_tags()
                all_series = await client.get_all_series()
                # Build a lookup: tag_id -> count of series using it
                tag_counts: dict = {}
                for s in all_series:
                    for tid in s.get("tags", []):
                        tag_counts[tid] = tag_counts.get(tid, 0) + 1
                tags = [
                    {"id": t["id"], "label": t["label"], "count": tag_counts.get(t["id"], 0)}
                    for t in raw_tags
                ]
            finally:
                await client.close()
        elif service == "radarr" and settings.radarr_url and settings.radarr_api_key:
            client = RadarrClient(settings.radarr_url, settings.radarr_api_key)
            try:
                raw_tags = await client.get_tags()
                all_movies = await client.get_all_movies()
                tag_counts: dict = {}
                for m in all_movies:
                    for tid in m.get("tags", []):
                        tag_counts[tid] = tag_counts.get(tid, 0) + 1
                tags = [
                    {"id": t["id"], "label": t["label"], "count": tag_counts.get(t["id"], 0)}
                    for t in raw_tags
                ]
            finally:
                await client.close()
        else:
            error = f"{service.capitalize()} is not configured"
    except Exception as e:
        error = str(e)

    return templates.TemplateResponse(
        "partials/tags_list.html",
        {
            "request": request,
            "tags": tags,
            "service": service,
            "error": error,
        },
    )


@router.post("/tags/create", response_class=HTMLResponse, dependencies=[Depends(require_power_user)])
async def tags_create(
    request: Request,
    label: str = Form(...),
    service: str = Form(...),
):
    """Create a new tag in Sonarr or Radarr."""
    error = None
    try:
        label = label.strip().lower()
        if not label:
            error = "Tag name cannot be empty"
        elif service == "sonarr" and settings.sonarr_url and settings.sonarr_api_key:
            client = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
            try:
                await client.create_tag(label)
            finally:
                await client.close()
        elif service == "radarr" and settings.radarr_url and settings.radarr_api_key:
            client = RadarrClient(settings.radarr_url, settings.radarr_api_key)
            try:
                await client.create_tag(label)
            finally:
                await client.close()
        else:
            error = f"{service.capitalize()} is not configured"
    except Exception as e:
        error = str(e)

    if error:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": error},
        )

    return templates.TemplateResponse(
        "components/toast.html",
        {
            "request": request,
            "type": "success",
            "message": f"Tag '{label}' created in {service.capitalize()}",
        },
        headers={"HX-Trigger": f"tags-updated-{service}"},
    )


@router.delete(
    "/tags/{service}/{tag_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(require_power_user)],
)
async def tags_delete(
    request: Request,
    service: str,
    tag_id: int,
):
    """Delete a tag from Sonarr or Radarr."""
    error = None
    try:
        if service == "sonarr" and settings.sonarr_url and settings.sonarr_api_key:
            client = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
            try:
                await client.delete_tag(tag_id)
            finally:
                await client.close()
        elif service == "radarr" and settings.radarr_url and settings.radarr_api_key:
            client = RadarrClient(settings.radarr_url, settings.radarr_api_key)
            try:
                await client.delete_tag(tag_id)
            finally:
                await client.close()
        else:
            error = f"{service.capitalize()} is not configured"
    except Exception as e:
        error = str(e)

    if error:
        return templates.TemplateResponse(
            "components/toast.html",
            {"request": request, "type": "error", "message": error},
        )

    return templates.TemplateResponse(
        "components/toast.html",
        {
            "request": request,
            "type": "success",
            "message": "Tag deleted",
        },
        headers={"HX-Trigger": f"tags-updated-{service}"},
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
