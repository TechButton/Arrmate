"""Web routes for Arrmate HTMX interface."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ...clients.discovery import discover_services
from ...core.command_parser import CommandParser
from ...core.executor import Executor
from ...core.intent_engine import IntentEngine
from ...core.models import Intent

# Initialize router
router = APIRouter(prefix="/web", tags=["web"])

# Get templates directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Global components (shared with API)
parser: Optional[CommandParser] = None
engine: Optional[IntentEngine] = None
executor: Optional[Executor] = None


def get_parser() -> CommandParser:
    """Get or create command parser."""
    global parser
    if parser is None:
        parser = CommandParser()
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


# ===== HTMX Partial Routes =====


@router.post("/command/parse", response_class=HTMLResponse)
async def parse_command(request: Request, command: str = Form(...)):
    """Parse command and return preview HTML."""
    try:
        cmd_parser = get_parser()
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
        cmd_parser = get_parser()
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
    # TODO: Implement actual library fetching from services
    # For now, return placeholder data
    items = []
    has_more = False
    
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
    # TODO: Implement actual search using services
    # For now, return placeholder
    results = []
    
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
        # TODO: Implement actual add functionality
        # For now, return success
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "success",
                "message": f"Added {title} to library",
            },
            headers={"HX-Trigger": "library-updated"},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "type": "error",
                "message": f"Failed to add {title}: {str(e)}",
            },
        )
