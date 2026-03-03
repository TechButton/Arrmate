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
        default="qwen2.5:7b",
        description="Ollama model to use (must support tool calling, e.g. qwen2.5:7b, llama3.1:8b)",
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

    # Readarr settings (Project retired - support provided for existing instances)
    readarr_url: Optional[str] = Field(
        default=None, description="Readarr base URL (e.g., http://readarr:8787)"
    )
    readarr_api_key: Optional[str] = Field(default=None, description="Readarr API key")

    # Bazarr settings
    bazarr_url: Optional[str] = Field(
        default=None, description="Bazarr base URL (e.g., http://bazarr:6767)"
    )
    bazarr_api_key: Optional[str] = Field(default=None, description="Bazarr API key")

    # AudioBookshelf settings (Audiobook player/manager)
    audiobookshelf_url: Optional[str] = Field(
        default=None, description="AudioBookshelf base URL (e.g., http://audiobookshelf:13378)"
    )
    audiobookshelf_api_key: Optional[str] = Field(
        default=None, description="AudioBookshelf API token"
    )

    # LazyLibrarian settings (Books/Audiobooks with downloading)
    lazylibrarian_url: Optional[str] = Field(
        default=None, description="LazyLibrarian base URL (e.g., http://lazylibrarian:5299)"
    )
    lazylibrarian_api_key: Optional[str] = Field(
        default=None, description="LazyLibrarian API key"
    )

    # ReadMeABook settings (Audiobook automation & request management)
    readmeabook_url: Optional[str] = Field(
        default=None, description="ReadMeABook base URL (e.g., http://readmeabook:3030)"
    )
    readmeabook_api_key: Optional[str] = Field(
        default=None, description="ReadMeABook API token (Bearer token from login)"
    )

    # Plex Media Server
    plex_url: Optional[str] = Field(
        default=None, description="Plex base URL (e.g., http://plex:32400)"
    )
    plex_token: Optional[str] = Field(
        default=None, description="Plex authentication token (X-Plex-Token)"
    )

    # Authentication settings
    secret_key: str = Field(
        default="", description="Secret key for session signing (auto-generated if empty)"
    )
    auth_data_dir: str = Field(
        default="/data", description="Directory for auth credential storage"
    )

    # Docker service discovery
    docker_network: Optional[str] = Field(
        default=None, description="Docker network name for service discovery"
    )
    enable_service_discovery: bool = Field(
        default=True, description="Enable automatic service discovery"
    )

    # SABnzbd settings
    sabnzbd_url: Optional[str] = Field(
        default=None,
        description="SABnzbd base URL (e.g., http://sabnzbd:8080). "
        "Append /sabnzbd if your instance uses that URL base (e.g., http://sabnzbd:8080/sabnzbd).",
    )
    sabnzbd_api_key: Optional[str] = Field(default=None, description="SABnzbd API key")

    # NZBget settings
    nzbget_url: Optional[str] = Field(
        default=None, description="NZBget base URL (e.g., http://nzbget:6789)"
    )
    nzbget_username: Optional[str] = Field(default=None, description="NZBget username")
    nzbget_password: Optional[str] = Field(default=None, description="NZBget password")

    # qBittorrent settings
    qbittorrent_url: Optional[str] = Field(
        default=None, description="qBittorrent Web UI URL (e.g., http://qbittorrent:8080)"
    )
    qbittorrent_username: Optional[str] = Field(default=None, description="qBittorrent username")
    qbittorrent_password: Optional[str] = Field(default=None, description="qBittorrent password")

    # Transmission settings
    transmission_url: Optional[str] = Field(
        default=None, description="Transmission Web UI URL (e.g., http://transmission:9091)"
    )
    transmission_username: Optional[str] = Field(
        default=None, description="Transmission username (leave blank if no auth)"
    )
    transmission_password: Optional[str] = Field(
        default=None, description="Transmission password"
    )

    # Prowlarr settings
    prowlarr_url: Optional[str] = Field(
        default=None, description="Prowlarr base URL (e.g., http://prowlarr:9696)"
    )
    prowlarr_api_key: Optional[str] = Field(default=None, description="Prowlarr API key")

    # TMDB (The Movie Database) — powers the Discover page
    tmdb_api_key: Optional[str] = Field(
        default=None,
        description="TMDB API key for the Discover page (https://www.themoviedb.org/settings/api)",
    )
    lastfm_api_key: Optional[str] = Field(
        default=None,
        description="Last.fm API key for music discovery (https://www.last.fm/api/account/create)",
    )

    # Notification webhooks
    slack_webhook_url: Optional[str] = Field(
        default=None, description="Slack webhook URL for request notifications"
    )
    discord_webhook_url: Optional[str] = Field(
        default=None, description="Discord webhook URL for request notifications"
    )

    # Transcoding settings
    transcode_crf: int = Field(
        default=28,
        description="CRF quality for H265 encoding (18=high quality/large, 28=default, 32=small/lower quality)",
    )
    transcode_preset: str = Field(
        default="medium",
        description="ffmpeg encoding preset (ultrafast/fast/medium/slow/veryslow — slower = smaller file)",
    )


# Global settings instance
settings = Settings()
