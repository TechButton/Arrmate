"""Web routes for Arrmate HTMX interface."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ...auth import auth_manager
from ...auth.dependencies import require_auth, safe_next_url
from ...auth.session import (
    clear_session_cookie,
    create_session_token,
    set_session_cookie,
)
from ...clients.discovery import discover_services, get_client_for_media_type
from ...core.command_parser import CommandParser
from ...core.executor import Executor
from ...core.intent_engine import IntentEngine

logger = logging.getLogger(__name__)

# Protected router — all routes require auth when enabled
router = APIRouter(prefix="/web", tags=["web"], dependencies=[Depends(require_auth)])

# Auth router — login/logout routes (no auth dependency)
auth_router = APIRouter(prefix="/web", tags=["auth"])

# Get templates directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Make auth_manager available in all templates
templates.env.globals["auth_manager"] = auth_manager

# Global components (shared with API)
parser: Optional[CommandParser] = None
engine: Optional[IntentEngine] = None
executor: Optional[Executor] = None


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


# ===== Auth Routes (unprotected) =====


@auth_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = Query(default="/web/"), error: str = Query(default="")):
    """Login page."""
    # If auth not required, redirect to dashboard
    if not auth_manager.is_auth_required():
        return RedirectResponse(url="/web/", status_code=303)

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
    if auth_manager.verify(username, password):
        token = create_session_token(username, auth_manager.get_secret_key())
        redirect_url = safe_next_url(next)
        response = RedirectResponse(url=redirect_url, status_code=303)
        set_session_cookie(response, token)
        return response

    # Login failed
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
    """Log out and redirect to login or dashboard."""
    if auth_manager.is_auth_required():
        response = RedirectResponse(url="/web/login", status_code=303)
    else:
        response = RedirectResponse(url="/web/", status_code=303)
    clear_session_cookie(response)
    return response


# ===== Full Page Routes =====


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page with overview."""
    services = await discover_services()

    # Count available services
    available_count = sum(1 for s in services.values() if s.available)

    return templates.TemplateResponse(
        "pages/index.html",
        {
            "request": request,
            "services": services,
            "available_count": available_count,
            "total_count": len(services),
        },
    )


@router.get("/command", response_class=HTMLResponse)
async def command_page(request: Request):
    """Command input page."""
    return templates.TemplateResponse(
        "pages/command.html",
        {
            "request": request,
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
        },
    )


@router.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    """Help and documentation page."""
    return templates.TemplateResponse(
        "pages/help.html",
        {
            "request": request,
            "version": "0.2.0",
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page."""
    return templates.TemplateResponse(
        "pages/settings.html",
        {
            "request": request,
        },
    )


# ===== Settings Auth Actions =====


@router.post("/settings/auth/set", response_class=HTMLResponse)
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
    token = create_session_token(username.strip(), auth_manager.get_secret_key())
    response = templates.TemplateResponse(
        "partials/auth_settings.html",
        {"request": request, "auth_success": "Authentication enabled"},
    )
    set_session_cookie(response, token)
    return response


@router.post("/settings/auth/enable", response_class=HTMLResponse)
async def auth_enable(request: Request):
    """Re-enable auth."""
    auth_manager.enable()

    # Set session cookie so the current user stays logged in
    username = auth_manager.get_username()
    if username:
        token = create_session_token(username, auth_manager.get_secret_key())
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


@router.post("/settings/auth/disable", response_class=HTMLResponse)
async def auth_disable(request: Request):
    """Disable auth without deleting credentials."""
    auth_manager.disable()
    return templates.TemplateResponse(
        "partials/auth_settings.html",
        {"request": request, "auth_success": "Authentication disabled"},
    )


@router.post("/settings/auth/delete", response_class=HTMLResponse)
async def auth_delete(request: Request):
    """Delete all credentials."""
    auth_manager.delete()
    response = templates.TemplateResponse(
        "partials/auth_settings.html",
        {"request": request, "auth_success": "Credentials deleted"},
    )
    clear_session_cookie(response)
    return response


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
async def execute_command(request: Request, command: str = Form(...)):
    """Execute command and return result HTML with toast."""
    try:
        # Parse
        cmd_parser = await get_parser()
        intent = await cmd_parser.parse(command)

        # Enrich
        intent_engine = get_engine()
        enriched = await intent_engine.enrich(intent)

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
                    items.append({
                        "title": item.get("title", "Unknown"),
                        "media_type": "tv",
                        "monitored": item.get("monitored", False),
                        "status": item.get("status", ""),
                        "season_count": item.get("seasonCount") or item.get("statistics", {}).get("seasonCount"),
                        "episode_count": item.get("statistics", {}).get("episodeFileCount") or item.get("episodeCount"),
                    })
            elif media_type == "movie":
                raw_items = await client.get_all_movies()
                for item in raw_items:
                    items.append({
                        "title": item.get("title", "Unknown"),
                        "media_type": "movie",
                        "monitored": item.get("monitored", False),
                        "status": item.get("status", ""),
                        "year": item.get("year"),
                        "size": _format_size(item.get("sizeOnDisk", 0)),
                    })
        finally:
            await client.close()

        # Sort by title
        items.sort(key=lambda x: x["title"].lower())

        # Paginate
        start = (page - 1) * page_size
        end = start + page_size
        has_more = end < len(items)
        items = items[start:end]

    except ValueError as e:
        # Service not configured - return empty with message
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
            for item in raw_results[:20]:  # Limit to 20 results
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

                # Extract poster URL from images array
                images = item.get("images") or item.get("remotePoster")
                if isinstance(images, list):
                    for img in images:
                        if img.get("coverType") == "poster":
                            result["poster_url"] = img.get("remoteUrl") or img.get("url")
                            break
                elif isinstance(images, str):
                    result["poster_url"] = images

                # Extract rating
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
            # Search for the item
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

            # Get quality profiles and root folders
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
            {
                "request": request,
                "type": "error",
                "message": str(e),
            },
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


def _format_size(size_bytes: int) -> str:
    """Format bytes into a human-readable string."""
    if not size_bytes:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"
