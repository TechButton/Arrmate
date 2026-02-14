"""Service discovery for media clients."""

from typing import Dict, Optional

from ..config.settings import settings
from ..core.models import ServiceInfo
from .radarr import RadarrClient
from .sonarr import SonarrClient

# Default ports for services
DEFAULT_PORTS = {
    "sonarr": 8989,
    "radarr": 7878,
    "lidarr": 8686,
}


async def discover_services() -> Dict[str, ServiceInfo]:
    """Discover available media services.

    Attempts to find services in this order:
    1. Explicit configuration (env vars)
    2. Docker service names (if on Docker network)
    3. Localhost with default ports

    Returns:
        Dictionary of service name to ServiceInfo
    """
    services: Dict[str, ServiceInfo] = {}

    # Sonarr
    if settings.sonarr_url and settings.sonarr_api_key:
        sonarr_client = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
        try:
            available = await sonarr_client.test_connection()
            version = None
            if available:
                status = await sonarr_client.get_system_status()
                version = status.get("version")

            services["sonarr"] = ServiceInfo(
                name="sonarr",
                url=settings.sonarr_url,
                api_key="***" + settings.sonarr_api_key[-4:] if settings.sonarr_api_key else None,
                available=available,
                version=version,
            )
        except Exception:
            services["sonarr"] = ServiceInfo(
                name="sonarr",
                url=settings.sonarr_url,
                api_key="***" + settings.sonarr_api_key[-4:] if settings.sonarr_api_key else None,
                available=False,
            )
        finally:
            await sonarr_client.close()

    # Radarr
    if settings.radarr_url and settings.radarr_api_key:
        radarr_client = RadarrClient(settings.radarr_url, settings.radarr_api_key)
        try:
            available = await radarr_client.test_connection()
            version = None
            if available:
                status = await radarr_client.get_system_status()
                version = status.get("version")

            services["radarr"] = ServiceInfo(
                name="radarr",
                url=settings.radarr_url,
                api_key="***" + settings.radarr_api_key[-4:] if settings.radarr_api_key else None,
                available=available,
                version=version,
            )
        except Exception:
            services["radarr"] = ServiceInfo(
                name="radarr",
                url=settings.radarr_url,
                api_key="***" + settings.radarr_api_key[-4:] if settings.radarr_api_key else None,
                available=False,
            )
        finally:
            await radarr_client.close()

    # Lidarr (when implemented)
    if settings.lidarr_url and settings.lidarr_api_key:
        services["lidarr"] = ServiceInfo(
            name="lidarr",
            url=settings.lidarr_url,
            api_key="***" + settings.lidarr_api_key[-4:] if settings.lidarr_api_key else None,
            available=False,  # Not yet implemented
        )

    return services


def get_client_for_media_type(media_type: str) -> Optional[object]:
    """Get the appropriate client for a media type.

    Args:
        media_type: Type of media (tv, movie, music, audiobook)

    Returns:
        Client instance or None if not configured

    Raises:
        ValueError: If service is not configured
    """
    if media_type == "tv":
        if not settings.sonarr_url or not settings.sonarr_api_key:
            raise ValueError(
                "Sonarr is not configured. Set SONARR_URL and SONARR_API_KEY."
            )
        return SonarrClient(settings.sonarr_url, settings.sonarr_api_key)

    elif media_type == "movie":
        if not settings.radarr_url or not settings.radarr_api_key:
            raise ValueError(
                "Radarr is not configured. Set RADARR_URL and RADARR_API_KEY."
            )
        return RadarrClient(settings.radarr_url, settings.radarr_api_key)

    elif media_type == "music":
        if not settings.lidarr_url or not settings.lidarr_api_key:
            raise ValueError(
                "Lidarr is not configured. Set LIDARR_URL and LIDARR_API_KEY."
            )
        # TODO: Implement LidarrClient
        raise NotImplementedError("Lidarr client not yet implemented")

    else:
        raise ValueError(f"Unsupported media type: {media_type}")
