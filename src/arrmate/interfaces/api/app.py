"""FastAPI REST API interface for Arrmate."""

from pathlib import Path
from typing import Dict

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ...auth.dependencies import AuthRedirectException, require_api_auth
from ...clients.discovery import discover_services
from ...config.settings import settings
from ...core.command_parser import CommandParser
from ...core.executor import Executor
from ...core.intent_engine import IntentEngine
from ...core.models import ExecutionResult, ServiceInfo
from ..web.routes import auth_router, router as web_router

# API models
class CommandRequest(BaseModel):
    """Request model for command execution."""

    command: str = Field(..., description="Natural language command to execute")
    dry_run: bool = Field(
        default=False, description="Parse only, don't execute"
    )


class CommandResponse(BaseModel):
    """Response model for command execution."""

    success: bool = Field(description="Whether execution was successful")
    message: str = Field(description="Human-readable result message")
    intent: Dict = Field(description="Parsed intent")
    result: ExecutionResult | None = Field(
        default=None, description="Execution result (if not dry run)"
    )


# Initialize FastAPI app
app = FastAPI(
    title="Arrmate API",
    description="Natural language interface for media management",
    version="0.2.6",
)

# Mount static files
static_dir = Path(__file__).parent.parent / "web" / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Exception handler for auth redirects
@app.exception_handler(AuthRedirectException)
async def auth_redirect_handler(request: Request, exc: AuthRedirectException):
    if exc.is_htmx:
        return Response(status_code=200, headers={"HX-Redirect": exc.login_url})
    return RedirectResponse(url=exc.login_url, status_code=303)


# Include auth router first (unprotected login/logout routes)
app.include_router(auth_router)

# Include web router (protected routes)
app.include_router(web_router)

# Global components (initialized per request to avoid state issues)
parser = None
engine = None
executor = None


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize components on startup."""
    global parser, engine, executor
    # Discover services so the LLM prompt knows which ones are available
    services = await discover_services()
    available = [name for name, info in services.items() if info.available]
    parser = CommandParser(available_services=available or None)
    engine = IntentEngine()
    executor = Executor()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up on shutdown."""
    if parser:
        await parser.close()


@app.get("/")
async def root():
    """Root endpoint - redirect to web UI."""
    return RedirectResponse(url="/web/")


@app.get("/health")
async def health() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post(
    "/api/v1/execute",
    response_model=CommandResponse,
    dependencies=[Depends(require_api_auth)],
)
async def execute_command(request: CommandRequest) -> CommandResponse:
    """Execute a natural language command.

    Args:
        request: Command request with NL command

    Returns:
        Command response with results
    """
    try:
        # Parse command
        intent = await parser.parse(request.command)

        # If dry run, return parsed intent only
        if request.dry_run:
            return CommandResponse(
                success=True,
                message="Command parsed successfully (dry run)",
                intent=intent.model_dump(),
                result=None,
            )

        # Enrich intent
        enriched_intent = await engine.enrich(intent)

        # Validate
        errors = engine.validate(enriched_intent)
        if errors:
            raise HTTPException(
                status_code=400,
                detail={"message": "Validation failed", "errors": errors},
            )

        # Execute
        result = await executor.execute(enriched_intent)

        return CommandResponse(
            success=result.success,
            message=result.message,
            intent=enriched_intent.model_dump(),
            result=result,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/v1/services",
    response_model=Dict[str, ServiceInfo],
    dependencies=[Depends(require_api_auth)],
)
async def get_services() -> Dict[str, ServiceInfo]:
    """Get status of all configured media services.

    Returns:
        Dictionary of service name to ServiceInfo
    """
    try:
        services = await discover_services()
        return services
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/v1/config",
    dependencies=[Depends(require_api_auth)],
)
async def get_config() -> Dict[str, str]:
    """Get current configuration (sanitized).

    Returns:
        Configuration dictionary
    """
    config = {
        "llm_provider": settings.llm_provider,
        "log_level": settings.log_level,
        "api_port": str(settings.api_port),
    }

    if settings.llm_provider == "ollama":
        config["ollama_url"] = settings.ollama_base_url
        config["ollama_model"] = settings.ollama_model
    elif settings.llm_provider == "openai":
        config["openai_model"] = settings.openai_model
    elif settings.llm_provider == "anthropic":
        config["anthropic_model"] = settings.anthropic_model

    return config


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
