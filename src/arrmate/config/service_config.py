"""Persistence layer for service settings (saved to /data/services.json).

Settings priority:
  1. Environment variables (set at container launch, always win at startup)
  2. /data/services.json (written by the Settings UI, applied at startup for
     fields that env vars left empty)
  3. Pydantic field defaults

When the UI saves a value it is applied to the running settings object immediately
(no restart needed) AND written to services.json so it survives restarts.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Every field that can be edited through the Settings UI
CONFIGURABLE_FIELDS: set[str] = {
    # LLM
    "llm_provider",
    "ollama_base_url",
    "ollama_model",
    "openai_api_key",
    "openai_model",
    "openai_base_url",
    "anthropic_api_key",
    "anthropic_model",
    # Media services
    "sonarr_url", "sonarr_api_key",
    "radarr_url", "radarr_api_key",
    "lidarr_url", "lidarr_api_key",
    "bazarr_url", "bazarr_api_key",
    "plex_url", "plex_token",
    "audiobookshelf_url", "audiobookshelf_api_key",
    "lazylibrarian_url", "lazylibrarian_api_key",
    "readmeabook_url", "readmeabook_api_key",
    # External APIs
    "tmdb_api_key",
    # Download clients
    "sabnzbd_url", "sabnzbd_api_key",
    "nzbget_url", "nzbget_username", "nzbget_password",
    "qbittorrent_url", "qbittorrent_username", "qbittorrent_password",
    "transmission_url", "transmission_username", "transmission_password",
    # Notification webhooks
    "slack_webhook_url",
    "discord_webhook_url",
    # General
    "arrmate_base_url",
    # Plex SSO
    "plex_sso_enabled",
    "plex_sso_default_role",
    "plex_sso_require_approval",
    "plex_sso_verify_plex_friends",
}


def _config_path() -> Path:
    from .settings import settings
    return Path(settings.auth_data_dir) / "services.json"


def _load_json() -> dict:
    path = _config_path()
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception as e:
            logger.warning(f"Could not read services.json: {e}")
    return {}


def apply_saved_config() -> None:
    """Apply services.json to settings for fields that env vars left empty.

    Call once at startup, after Pydantic has already loaded env vars.
    """
    from .settings import settings

    saved = _load_json()
    for key, value in saved.items():
        if key not in CONFIGURABLE_FIELDS or not hasattr(settings, key):
            continue
        # Only fill in if env var left the field empty / None
        if not getattr(settings, key, None) and value:
            try:
                setattr(settings, key, value)
            except Exception:
                pass


def save_service_config(updates: dict[str, Any]) -> None:
    """Persist updates to services.json and apply them to settings in memory.

    Empty strings are treated as None (field cleared).
    """
    from .settings import settings

    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Bool fields in the set — checkboxes send "on" when checked, absent when unchecked.
    # We handle them separately so unchecked boxes (missing from form) can be cleared.
    _BOOL_FIELDS = {"plex_sso_enabled", "plex_sso_require_approval", "plex_sso_verify_plex_friends"}

    existing = _load_json()

    # First pass: explicit values from form
    for key, value in updates.items():
        if key not in CONFIGURABLE_FIELDS:
            continue
        if key in _BOOL_FIELDS:
            normalized: Any = value in ("on", "true", "1", True)
        else:
            normalized = value.strip() if isinstance(value, str) else value
            if not normalized:
                normalized = None
        existing[key] = normalized
        if hasattr(settings, key):
            try:
                setattr(settings, key, normalized)
            except Exception:
                pass

    # Second pass: bool fields absent from form → False (unchecked checkbox)
    for key in _BOOL_FIELDS:
        if key in CONFIGURABLE_FIELDS and key not in updates:
            existing[key] = False
            if hasattr(settings, key):
                try:
                    setattr(settings, key, False)
                except Exception:
                    pass

    path.write_text(json.dumps(existing, indent=2))


def get_service_config() -> dict[str, Any]:
    """Return current settings values for all configurable fields."""
    from .settings import settings

    return {field: getattr(settings, field, None) for field in CONFIGURABLE_FIELDS}
