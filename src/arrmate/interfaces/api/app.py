"""FastAPI REST API interface for Arrmate."""

from typing import Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ...clients.discovery import discover_services
from ...config.settings import settings
from ...core.command_parser import CommandParser
from ...core.executor import Executor
from ...core.intent_engine import IntentEngine
from ...core.models import ExecutionResult, ServiceInfo

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
    version="0.1.0",
)

# Global components (initialized per request to avoid state issues)
parser = None
engine = None
executor = None


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize components on startup."""
    global parser, engine, executor
    parser = CommandParser()
    engine = IntentEngine()
    executor = Executor()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up on shutdown."""
    if parser:
        await parser.close()


@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Arrmate API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/api/v1/execute", response_model=CommandResponse)
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


@app.get("/api/v1/services", response_model=Dict[str, ServiceInfo])
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


@app.get("/api/v1/config")
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
