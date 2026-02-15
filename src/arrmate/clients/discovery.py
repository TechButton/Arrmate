"""Service discovery for media clients."""

import logging
from typing import Dict, Optional

from ..config.settings import settings
from ..core.models import (
    EnhancedServiceInfo,
    ImplementationStatus,
    ServiceCapability,
    ServiceInfo,
)
from .audiobookshelf import AudioBookshelfClient
from .bazarr import BazarrClient
from .huntarr import HuntarrClient
from .lazylibrarian import LazyLibrarianClient
from .lidarr import LidarrClient
from .plex import PlexClient
from .radarr import RadarrClient
from .readarr import ReadarrClient
from .sonarr import SonarrClient
from .whisparr import WhisparrClient

logger = logging.getLogger(__name__)

# Default ports for services
DEFAULT_PORTS = {
    "sonarr": 8989,
    "radarr": 7878,
    "lidarr": 8686,
    "readarr": 8787,
    "whisparr": 6969,
    "bazarr": 6767,
    "audiobookshelf": 13378,
    "lazylibrarian": 5299,
    "huntarr": 3000,
    "plex": 32400,
}


def _mask_api_key(api_key: Optional[str]) -> Optional[str]:
    """Mask an API key for display.

    Args:
        api_key: API key to mask

    Returns:
        Masked API key showing only last 4 characters
    """
    if not api_key or len(api_key) < 4:
        return None
    return "***" + api_key[-4:]


def _get_implementation_status(service_name: str) -> ImplementationStatus:
    """Get implementation status for a service.

    Args:
        service_name: Name of the service

    Returns:
        Implementation status
    """
    status_map = {
        "sonarr": ImplementationStatus.COMPLETE,
        "radarr": ImplementationStatus.COMPLETE,
        "lidarr": ImplementationStatus.PARTIAL,
        "readarr": ImplementationStatus.DEPRECATED,
        "whisparr": ImplementationStatus.PARTIAL,
        "bazarr": ImplementationStatus.PARTIAL,
        "audiobookshelf": ImplementationStatus.PARTIAL,
        "lazylibrarian": ImplementationStatus.PARTIAL,
        "huntarr": ImplementationStatus.PARTIAL,
        "plex": ImplementationStatus.PARTIAL,
    }
    return status_map.get(service_name, ImplementationStatus.PLANNED)


def _get_api_version(service_name: str) -> str:
    """Get API version for a service.

    Args:
        service_name: Name of the service

    Returns:
        API version string
    """
    version_map = {
        "sonarr": "v3",
        "radarr": "v3",
        "lidarr": "v3",
        "readarr": "v1",
        "whisparr": "v3",
        "bazarr": "custom",
        "audiobookshelf": "REST",
        "lazylibrarian": "custom",
        "huntarr": "REST",
        "plex": "REST",
    }
    return version_map.get(service_name, "unknown")


def _get_media_type(service_name: str) -> str:
    """Get media type for a service.

    Args:
        service_name: Name of the service

    Returns:
        Media type string
    """
    media_type_map = {
        "sonarr": "TV Shows",
        "radarr": "Movies",
        "lidarr": "Music",
        "readarr": "Books/Audiobooks",
        "whisparr": "Adult Content",
        "bazarr": "Subtitles",
        "audiobookshelf": "Audiobooks/Podcasts",
        "lazylibrarian": "Books/Audiobooks",
        "huntarr": "Orchestration",
        "plex": "Media Server",
    }
    return media_type_map.get(service_name, "Unknown")


def _get_capabilities(service_name: str) -> ServiceCapability:
    """Get service capabilities.

    Args:
        service_name: Name of the service

    Returns:
        ServiceCapability object
    """
    # Full capabilities for complete implementations
    if service_name in ["sonarr", "radarr"]:
        return ServiceCapability(
            can_search=True,
            can_add=True,
            can_remove=True,
            can_upgrade=True,
            can_list=True,
        )

    # Standard capabilities for v3 services
    if service_name in ["lidarr", "whisparr"]:
        return ServiceCapability(
            can_search=True,
            can_add=True,
            can_remove=True,
            can_upgrade=False,  # Not yet implemented
            can_list=True,
        )

    # Limited capabilities for deprecated Readarr
    if service_name == "readarr":
        return ServiceCapability(
            can_search=True,
            can_add=True,
            can_remove=True,
            can_upgrade=False,
            can_list=True,
        )

    # Companion service capabilities (Bazarr)
    if service_name == "bazarr":
        return ServiceCapability(
            can_search=True,  # Search subtitles
            can_add=False,  # Doesn't add media
            can_remove=False,  # Doesn't remove media
            can_upgrade=False,
            can_list=True,  # List missing subtitles
        )

    # AudioBookshelf capabilities
    if service_name == "audiobookshelf":
        return ServiceCapability(
            can_search=True,
            can_add=False,  # Manual upload only
            can_remove=True,
            can_upgrade=False,
            can_list=True,
        )

    # LazyLibrarian capabilities
    if service_name == "lazylibrarian":
        return ServiceCapability(
            can_search=True,
            can_add=True,
            can_remove=True,
            can_upgrade=False,
            can_list=True,
        )

    # huntarr.io capabilities (orchestration)
    if service_name == "huntarr":
        return ServiceCapability(
            can_search=False,  # Doesn't search directly
            can_add=False,  # Manages other services
            can_remove=False,
            can_upgrade=False,
            can_list=True,  # Lists stats/instances
        )

    # Plex capabilities (media server/player)
    if service_name == "plex":
        return ServiceCapability(
            can_search=True,
            can_add=False,  # Doesn't download or add content
            can_remove=True,  # Can delete to trash
            can_upgrade=False,
            can_list=True,
        )

    return ServiceCapability()


async def discover_services() -> Dict[str, EnhancedServiceInfo]:
    """Discover available media services.

    Attempts to find services in this order:
    1. Explicit configuration (env vars)
    2. Docker service names (if on Docker network)
    3. Localhost with default ports

    Returns:
        Dictionary of service name to EnhancedServiceInfo
    """
    services: Dict[str, EnhancedServiceInfo] = {}

    # Sonarr
    if settings.sonarr_url and settings.sonarr_api_key:
        client = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
        try:
            available = await client.test_connection()
            version = None
            if available:
                status = await client.get_system_status()
                version = status.get("version")

            services["sonarr"] = EnhancedServiceInfo(
                name="sonarr",
                url=settings.sonarr_url,
                api_key=_mask_api_key(settings.sonarr_api_key),
                available=available,
                version=version,
                implementation_status=_get_implementation_status("sonarr"),
                api_version=_get_api_version("sonarr"),
                capabilities=_get_capabilities("sonarr"),
                media_type=_get_media_type("sonarr"),
                is_deprecated=False,
            )
        except Exception as e:
            logger.error(f"Error discovering Sonarr: {e}")
            services["sonarr"] = EnhancedServiceInfo(
                name="sonarr",
                url=settings.sonarr_url,
                api_key=_mask_api_key(settings.sonarr_api_key),
                available=False,
                implementation_status=_get_implementation_status("sonarr"),
                api_version=_get_api_version("sonarr"),
                capabilities=_get_capabilities("sonarr"),
                media_type=_get_media_type("sonarr"),
                is_deprecated=False,
            )
        finally:
            await client.close()

    # Radarr
    if settings.radarr_url and settings.radarr_api_key:
        client = RadarrClient(settings.radarr_url, settings.radarr_api_key)
        try:
            available = await client.test_connection()
            version = None
            if available:
                status = await client.get_system_status()
                version = status.get("version")

            services["radarr"] = EnhancedServiceInfo(
                name="radarr",
                url=settings.radarr_url,
                api_key=_mask_api_key(settings.radarr_api_key),
                available=available,
                version=version,
                implementation_status=_get_implementation_status("radarr"),
                api_version=_get_api_version("radarr"),
                capabilities=_get_capabilities("radarr"),
                media_type=_get_media_type("radarr"),
                is_deprecated=False,
            )
        except Exception as e:
            logger.error(f"Error discovering Radarr: {e}")
            services["radarr"] = EnhancedServiceInfo(
                name="radarr",
                url=settings.radarr_url,
                api_key=_mask_api_key(settings.radarr_api_key),
                available=False,
                implementation_status=_get_implementation_status("radarr"),
                api_version=_get_api_version("radarr"),
                capabilities=_get_capabilities("radarr"),
                media_type=_get_media_type("radarr"),
                is_deprecated=False,
            )
        finally:
            await client.close()

    # Lidarr
    if settings.lidarr_url and settings.lidarr_api_key:
        client = LidarrClient(settings.lidarr_url, settings.lidarr_api_key)
        try:
            available = await client.test_connection()
            version = None
            if available:
                status = await client.get_system_status()
                version = status.get("version")

            services["lidarr"] = EnhancedServiceInfo(
                name="lidarr",
                url=settings.lidarr_url,
                api_key=_mask_api_key(settings.lidarr_api_key),
                available=available,
                version=version,
                implementation_status=_get_implementation_status("lidarr"),
                api_version=_get_api_version("lidarr"),
                capabilities=_get_capabilities("lidarr"),
                media_type=_get_media_type("lidarr"),
                is_deprecated=False,
            )
        except Exception as e:
            logger.error(f"Error discovering Lidarr: {e}")
            services["lidarr"] = EnhancedServiceInfo(
                name="lidarr",
                url=settings.lidarr_url,
                api_key=_mask_api_key(settings.lidarr_api_key),
                available=False,
                implementation_status=_get_implementation_status("lidarr"),
                api_version=_get_api_version("lidarr"),
                capabilities=_get_capabilities("lidarr"),
                media_type=_get_media_type("lidarr"),
                is_deprecated=False,
            )
        finally:
            await client.close()

    # Readarr (Deprecated)
    if settings.readarr_url and settings.readarr_api_key:
        client = ReadarrClient(settings.readarr_url, settings.readarr_api_key)
        try:
            available = await client.test_connection()
            version = None
            if available:
                status = await client.get_system_status()
                version = status.get("version")

            services["readarr"] = EnhancedServiceInfo(
                name="readarr",
                url=settings.readarr_url,
                api_key=_mask_api_key(settings.readarr_api_key),
                available=available,
                version=version,
                implementation_status=_get_implementation_status("readarr"),
                api_version=_get_api_version("readarr"),
                capabilities=_get_capabilities("readarr"),
                media_type=_get_media_type("readarr"),
                is_deprecated=True,
                deprecation_message="Readarr project is retired. Support limited to existing instances.",
            )
        except Exception as e:
            logger.error(f"Error discovering Readarr: {e}")
            services["readarr"] = EnhancedServiceInfo(
                name="readarr",
                url=settings.readarr_url,
                api_key=_mask_api_key(settings.readarr_api_key),
                available=False,
                implementation_status=_get_implementation_status("readarr"),
                api_version=_get_api_version("readarr"),
                capabilities=_get_capabilities("readarr"),
                media_type=_get_media_type("readarr"),
                is_deprecated=True,
                deprecation_message="Readarr project is retired. Support limited to existing instances.",
            )
        finally:
            await client.close()

    # Whisparr
    if settings.whisparr_url and settings.whisparr_api_key:
        client = WhisparrClient(settings.whisparr_url, settings.whisparr_api_key)
        try:
            available = await client.test_connection()
            version = None
            if available:
                status = await client.get_system_status()
                version = status.get("version")

            services["whisparr"] = EnhancedServiceInfo(
                name="whisparr",
                url=settings.whisparr_url,
                api_key=_mask_api_key(settings.whisparr_api_key),
                available=available,
                version=version,
                implementation_status=_get_implementation_status("whisparr"),
                api_version=_get_api_version("whisparr"),
                capabilities=_get_capabilities("whisparr"),
                media_type=_get_media_type("whisparr"),
                is_deprecated=False,
            )
        except Exception as e:
            logger.error(f"Error discovering Whisparr: {e}")
            services["whisparr"] = EnhancedServiceInfo(
                name="whisparr",
                url=settings.whisparr_url,
                api_key=_mask_api_key(settings.whisparr_api_key),
                available=False,
                implementation_status=_get_implementation_status("whisparr"),
                api_version=_get_api_version("whisparr"),
                capabilities=_get_capabilities("whisparr"),
                media_type=_get_media_type("whisparr"),
                is_deprecated=False,
            )
        finally:
            await client.close()

    # Bazarr (Companion Service)
    if settings.bazarr_url and settings.bazarr_api_key:
        client = BazarrClient(settings.bazarr_url, settings.bazarr_api_key)
        try:
            available = await client.test_connection()
            version = None
            if available:
                status = await client.get_system_status()
                version = status.get("data", {}).get("bazarr_version")

            services["bazarr"] = EnhancedServiceInfo(
                name="bazarr",
                url=settings.bazarr_url,
                api_key=_mask_api_key(settings.bazarr_api_key),
                available=available,
                version=version,
                implementation_status=_get_implementation_status("bazarr"),
                api_version=_get_api_version("bazarr"),
                capabilities=_get_capabilities("bazarr"),
                media_type=_get_media_type("bazarr"),
                is_deprecated=False,
            )
        except Exception as e:
            logger.error(f"Error discovering Bazarr: {e}")
            services["bazarr"] = EnhancedServiceInfo(
                name="bazarr",
                url=settings.bazarr_url,
                api_key=_mask_api_key(settings.bazarr_api_key),
                available=False,
                implementation_status=_get_implementation_status("bazarr"),
                api_version=_get_api_version("bazarr"),
                capabilities=_get_capabilities("bazarr"),
                media_type=_get_media_type("bazarr"),
                is_deprecated=False,
            )
        finally:
            await client.close()

    # AudioBookshelf (Audiobook Player)
    if settings.audiobookshelf_url and settings.audiobookshelf_api_key:
        client = AudioBookshelfClient(
            settings.audiobookshelf_url, settings.audiobookshelf_api_key
        )
        try:
            available = await client.test_connection()
            version = None
            if available:
                try:
                    status = await client.get_system_status()
                    version = status.get("serverVersion") or status.get("version")
                except Exception:
                    pass  # Version not critical

            services["audiobookshelf"] = EnhancedServiceInfo(
                name="audiobookshelf",
                url=settings.audiobookshelf_url,
                api_key=_mask_api_key(settings.audiobookshelf_api_key),
                available=available,
                version=version,
                implementation_status=_get_implementation_status("audiobookshelf"),
                api_version=_get_api_version("audiobookshelf"),
                capabilities=_get_capabilities("audiobookshelf"),
                media_type=_get_media_type("audiobookshelf"),
                is_deprecated=False,
            )
        except Exception as e:
            logger.error(f"Error discovering AudioBookshelf: {e}")
            services["audiobookshelf"] = EnhancedServiceInfo(
                name="audiobookshelf",
                url=settings.audiobookshelf_url,
                api_key=_mask_api_key(settings.audiobookshelf_api_key),
                available=False,
                implementation_status=_get_implementation_status("audiobookshelf"),
                api_version=_get_api_version("audiobookshelf"),
                capabilities=_get_capabilities("audiobookshelf"),
                media_type=_get_media_type("audiobookshelf"),
                is_deprecated=False,
            )
        finally:
            await client.close()

    # LazyLibrarian (Books/Audiobooks with downloading)
    if settings.lazylibrarian_url and settings.lazylibrarian_api_key:
        client = LazyLibrarianClient(
            settings.lazylibrarian_url, settings.lazylibrarian_api_key
        )
        try:
            available = await client.test_connection()
            version = None
            if available:
                try:
                    status = await client.get_system_status()
                    version = status.get("version")
                except Exception:
                    pass

            services["lazylibrarian"] = EnhancedServiceInfo(
                name="lazylibrarian",
                url=settings.lazylibrarian_url,
                api_key=_mask_api_key(settings.lazylibrarian_api_key),
                available=available,
                version=version,
                implementation_status=_get_implementation_status("lazylibrarian"),
                api_version=_get_api_version("lazylibrarian"),
                capabilities=_get_capabilities("lazylibrarian"),
                media_type=_get_media_type("lazylibrarian"),
                is_deprecated=False,
            )
        except Exception as e:
            logger.error(f"Error discovering LazyLibrarian: {e}")
            services["lazylibrarian"] = EnhancedServiceInfo(
                name="lazylibrarian",
                url=settings.lazylibrarian_url,
                api_key=_mask_api_key(settings.lazylibrarian_api_key),
                available=False,
                implementation_status=_get_implementation_status("lazylibrarian"),
                api_version=_get_api_version("lazylibrarian"),
                capabilities=_get_capabilities("lazylibrarian"),
                media_type=_get_media_type("lazylibrarian"),
                is_deprecated=False,
            )
        finally:
            await client.close()

    # huntarr.io (Orchestration Service)
    if settings.huntarr_url and settings.huntarr_api_key:
        client = HuntarrClient(settings.huntarr_url, settings.huntarr_api_key)
        try:
            available = await client.test_connection()
            version = None
            if available:
                try:
                    stats = await client.get_stats()
                    version = stats.get("data", {}).get("version")
                except Exception:
                    pass

            services["huntarr"] = EnhancedServiceInfo(
                name="huntarr",
                url=settings.huntarr_url,
                api_key=_mask_api_key(settings.huntarr_api_key),
                available=available,
                version=version,
                implementation_status=_get_implementation_status("huntarr"),
                api_version=_get_api_version("huntarr"),
                capabilities=_get_capabilities("huntarr"),
                media_type=_get_media_type("huntarr"),
                is_deprecated=False,
            )
        except Exception as e:
            logger.error(f"Error discovering huntarr.io: {e}")
            services["huntarr"] = EnhancedServiceInfo(
                name="huntarr",
                url=settings.huntarr_url,
                api_key=_mask_api_key(settings.huntarr_api_key),
                available=False,
                implementation_status=_get_implementation_status("huntarr"),
                api_version=_get_api_version("huntarr"),
                capabilities=_get_capabilities("huntarr"),
                media_type=_get_media_type("huntarr"),
                is_deprecated=False,
            )
        finally:
            await client.close()

    # Plex Media Server
    if settings.plex_url and settings.plex_token:
        client = PlexClient(settings.plex_url, settings.plex_token)
        try:
            available = await client.test_connection()
            version = None
            if available:
                try:
                    version = await client.get_version()
                except Exception:
                    pass

            services["plex"] = EnhancedServiceInfo(
                name="plex",
                url=settings.plex_url,
                api_key=_mask_api_key(settings.plex_token),
                available=available,
                version=version,
                implementation_status=_get_implementation_status("plex"),
                api_version=_get_api_version("plex"),
                capabilities=_get_capabilities("plex"),
                media_type=_get_media_type("plex"),
                is_deprecated=False,
            )
        except Exception as e:
            logger.error(f"Error discovering Plex: {e}")
            services["plex"] = EnhancedServiceInfo(
                name="plex",
                url=settings.plex_url,
                api_key=_mask_api_key(settings.plex_token),
                available=False,
                implementation_status=_get_implementation_status("plex"),
                api_version=_get_api_version("plex"),
                capabilities=_get_capabilities("plex"),
                media_type=_get_media_type("plex"),
                is_deprecated=False,
            )
        finally:
            await client.close()

    return services


def get_client_for_media_type(media_type: str) -> Optional[object]:
    """Get the appropriate client for a media type.

    Args:
        media_type: Type of media (tv, movie, music, audiobook, book, adult)

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
        return LidarrClient(settings.lidarr_url, settings.lidarr_api_key)

    elif media_type in ("audiobook", "book"):
        if not settings.readarr_url or not settings.readarr_api_key:
            raise ValueError(
                "Readarr is not configured. Set READARR_URL and READARR_API_KEY."
            )
        logger.warning(
            "Using deprecated Readarr client. Project is retired. "
            "Consider alternatives like Calibre-Web or LazyLibrarian."
        )
        return ReadarrClient(settings.readarr_url, settings.readarr_api_key)

    elif media_type == "adult":
        if not settings.whisparr_url or not settings.whisparr_api_key:
            raise ValueError(
                "Whisparr is not configured. Set WHISPARR_URL and WHISPARR_API_KEY."
            )
        return WhisparrClient(settings.whisparr_url, settings.whisparr_api_key)

    else:
        raise ValueError(f"Unsupported media type: {media_type}")
