"""Core data models for Arrmate."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MediaType(str, Enum):
    """Type of media being managed."""

    TV = "tv"
    MOVIE = "movie"
    MUSIC = "music"
    AUDIOBOOK = "audiobook"


class ActionType(str, Enum):
    """Type of action to perform on media."""

    REMOVE = "remove"
    SEARCH = "search"
    ADD = "add"
    UPGRADE = "upgrade"
    LIST = "list"
    INFO = "info"
    DELETE = "delete"


class Intent(BaseModel):
    """Structured representation of user intent extracted from natural language."""

    action: ActionType = Field(description="The action to perform")
    media_type: MediaType = Field(description="Type of media (TV, movie, music, etc.)")
    title: Optional[str] = Field(default=None, description="Title of the media item")
    season: Optional[int] = Field(default=None, description="Season number (TV shows only)")
    episodes: Optional[List[int]] = Field(
        default=None, description="Episode numbers (TV shows only)"
    )
    criteria: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Search/filter criteria (language, quality, etc.)",
    )
    item_id: Optional[int] = Field(
        default=None, description="Internal ID of the media item (populated during enrichment)"
    )
    series_id: Optional[int] = Field(
        default=None, description="Internal series ID (TV shows only)"
    )

    class Config:
        """Pydantic config."""

        use_enum_values = True


class ExecutionResult(BaseModel):
    """Result of executing an intent."""

    success: bool = Field(description="Whether the execution was successful")
    message: str = Field(description="Human-readable message about the result")
    data: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional data returned from execution"
    )
    errors: Optional[List[str]] = Field(default=None, description="List of errors if any")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Successfully removed 2 episodes from Angel Season 1",
                "data": {"removed_files": ["episode1.mkv", "episode2.mkv"]},
                "errors": None,
            }
        }


class ServiceInfo(BaseModel):
    """Information about a discovered media service."""

    name: str = Field(description="Service name (sonarr, radarr, lidarr)")
    url: str = Field(description="Base URL of the service")
    api_key: Optional[str] = Field(default=None, description="API key (masked)")
    available: bool = Field(description="Whether the service is reachable")
    version: Optional[str] = Field(default=None, description="Service version")
