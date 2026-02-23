"""TMDB (The Movie Database) API client.

Used to power the Discover page — trending, upcoming, popular, and on-the-air
content that users can add directly to Radarr/Sonarr.
"""

from typing import Any, Dict, List, Optional

import httpx


class TMDBClient:
    """Client for the TMDB v3 API."""

    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE = "https://image.tmdb.org/t/p"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if params is None:
            params = {}
        params["api_key"] = self.api_key
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def poster_url(self, path: str | None, size: str = "w342") -> str | None:
        """Return the full poster URL for a given TMDB poster path."""
        if not path:
            return None
        return f"{self.IMAGE_BASE}/{size}{path}"

    async def test_connection(self) -> bool:
        try:
            await self._get("configuration")
            return True
        except Exception:
            return False

    # ── Movies ────────────────────────────────────────────────────────────────

    async def get_trending_movies(self, time_window: str = "week") -> List[Dict]:
        """Trending movies over the last day or week."""
        data = await self._get(f"trending/movie/{time_window}", {"language": "en-US"})
        return data.get("results", [])

    async def get_upcoming_movies(self) -> List[Dict]:
        """Movies with a future release date (US region)."""
        data = await self._get("movie/upcoming", {"language": "en-US", "region": "US"})
        return data.get("results", [])

    async def get_now_playing(self) -> List[Dict]:
        """Movies currently in theatres (US region)."""
        data = await self._get("movie/now_playing", {"language": "en-US", "region": "US"})
        return data.get("results", [])

    async def get_popular_movies(self) -> List[Dict]:
        """Most popular movies right now."""
        data = await self._get("movie/popular", {"language": "en-US"})
        return data.get("results", [])

    async def get_top_rated_movies(self) -> List[Dict]:
        """Top-rated movies of all time."""
        data = await self._get("movie/top_rated", {"language": "en-US"})
        return data.get("results", [])

    # ── TV Shows ──────────────────────────────────────────────────────────────

    async def get_trending_tv(self, time_window: str = "week") -> List[Dict]:
        """Trending TV shows over the last day or week."""
        data = await self._get(f"trending/tv/{time_window}", {"language": "en-US"})
        return data.get("results", [])

    async def get_tv_airing_today(self) -> List[Dict]:
        """TV shows with episodes airing today."""
        data = await self._get("tv/airing_today", {"language": "en-US"})
        return data.get("results", [])

    async def get_tv_on_the_air(self) -> List[Dict]:
        """TV shows currently airing (next 7 days)."""
        data = await self._get("tv/on_the_air", {"language": "en-US"})
        return data.get("results", [])

    async def get_popular_tv(self) -> List[Dict]:
        """Most popular TV shows right now."""
        data = await self._get("tv/popular", {"language": "en-US"})
        return data.get("results", [])

    async def get_top_rated_tv(self) -> List[Dict]:
        """Top-rated TV shows of all time."""
        data = await self._get("tv/top_rated", {"language": "en-US"})
        return data.get("results", [])

    # ── Metadata helpers ──────────────────────────────────────────────────────

    async def get_external_ids(self, tmdb_id: int, media_type: str = "tv") -> Dict:
        """Get external IDs for a movie or TV show.

        For TV shows this includes the TVDB ID needed by Sonarr.
        """
        return await self._get(f"{media_type}/{tmdb_id}/external_ids")
