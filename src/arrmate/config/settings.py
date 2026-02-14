"""Configuration management using Pydantic Settings."""

from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = Field(default="Arrmate", description="Application name")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, description="API server port")

    # LLM Provider settings
    llm_provider: Literal["ollama", "openai", "anthropic"] = Field(
        default="ollama", description="LLM provider to use"
    )

    # Ollama settings
    ollama_base_url: str = Field(
        default="http://localhost:11434", description="Ollama API base URL"
    )
    ollama_model: str = Field(
        default="llama3.1:latest", description="Ollama model to use"
    )

    # OpenAI settings
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openai_model: str = Field(default="gpt-4-turbo-preview", description="OpenAI model to use")
    openai_base_url: Optional[str] = Field(
        default=None, description="Custom OpenAI API base URL"
    )

    # Anthropic settings
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    anthropic_model: str = Field(
        default="claude-3-5-sonnet-20241022", description="Anthropic model to use"
    )

    # Sonarr settings
    sonarr_url: Optional[str] = Field(
        default=None, description="Sonarr base URL (e.g., http://sonarr:8989)"
    )
    sonarr_api_key: Optional[str] = Field(default=None, description="Sonarr API key")

    # Radarr settings
    radarr_url: Optional[str] = Field(
        default=None, description="Radarr base URL (e.g., http://radarr:7878)"
    )
    radarr_api_key: Optional[str] = Field(default=None, description="Radarr API key")

    # Lidarr settings
    lidarr_url: Optional[str] = Field(
        default=None, description="Lidarr base URL (e.g., http://lidarr:8686)"
    )
    lidarr_api_key: Optional[str] = Field(default=None, description="Lidarr API key")

    # Docker service discovery
    docker_network: Optional[str] = Field(
        default=None, description="Docker network name for service discovery"
    )
    enable_service_discovery: bool = Field(
        default=True, description="Enable automatic service discovery"
    )


# Global settings instance
settings = Settings()
