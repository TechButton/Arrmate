"""Bazarr API client implementation.

Bazarr is a companion service that manages subtitles for Sonarr and Radarr.
It integrates with existing Sonarr/Radarr instances to download and manage
subtitle files for movies and TV shows.
"""

from typing import Any, Dict, List, Optional

from .base_companion import BaseCompanionClient


class BazarrClient(BaseCompanionClient):
    """Client for Bazarr API (Subtitle management).

    Bazarr works as a companion to Sonarr and Radarr, managing subtitle
    downloads for existing media in those libraries.
    """

    async def test_connection(self) -> bool:
        """Test connection to Bazarr.

        Returns:
            True if connection successful
        """
        try:
            await self.get_system_status()
            return True
        except Exception:
            return False

    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status and version.

        Returns:
            System status information including version
        """
        return await self._get("api/system/status")

    async def get_missing_items(self, service_type: str) -> List[Dict[str, Any]]:
        """Get items missing subtitles.

        Args:
            service_type: "sonarr" for episodes or "radarr" for movies

        Returns:
            List of items missing subtitles
        """
        if service_type.lower() == "sonarr":
            return await self.get_episodes_with_missing_subtitles()
        elif service_type.lower() == "radarr":
            return await self.get_movies_with_missing_subtitles()
        else:
            raise ValueError(f"Unsupported service type: {service_type}")

    async def get_episodes(self) -> List[Dict[str, Any]]:
        """Get all episodes tracked by Bazarr.

        Returns:
            List of all episodes
        """
        return await self._get("api/episodes")

    async def get_episodes_with_missing_subtitles(self) -> List[Dict[str, Any]]:
        """Get episodes that are missing subtitles.

        Returns:
            List of episodes with missing subtitles
        """
        all_episodes = await self.get_episodes()
        # Filter for episodes with missing subtitles
        return [
            ep
            for ep in all_episodes
            if ep.get("missing_subtitles") or not ep.get("subtitles")
        ]

    async def get_movies(self) -> List[Dict[str, Any]]:
        """Get all movies tracked by Bazarr.

        Returns:
            List of all movies
        """
        return await self._get("api/movies")

    async def get_movies_with_missing_subtitles(self) -> List[Dict[str, Any]]:
        """Get movies that are missing subtitles.

        Returns:
            List of movies with missing subtitles
        """
        all_movies = await self.get_movies()
        # Filter for movies with missing subtitles
        return [
            movie
            for movie in all_movies
            if movie.get("missing_subtitles") or not movie.get("subtitles")
        ]

    async def search_episode_subtitles(
        self, episode_id: int, language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for subtitles for an episode.

        Args:
            episode_id: Bazarr episode ID
            language: Language code (e.g., "en", "es") - optional

        Returns:
            List of available subtitles
        """
        params = {"episodeid": episode_id}
        if language:
            params["language"] = language
        return await self._post("api/episodes/search", data=params)

    async def search_movie_subtitles(
        self, movie_id: int, language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for subtitles for a movie.

        Args:
            movie_id: Bazarr movie ID
            language: Language code (e.g., "en", "es") - optional

        Returns:
            List of available subtitles
        """
        params = {"movieid": movie_id}
        if language:
            params["language"] = language
        return await self._post("api/movies/search", data=params)

    async def download_episode_subtitle(
        self, episode_id: int, subtitle_id: str, language: str
    ) -> Dict[str, Any]:
        """Download a subtitle for an episode.

        Args:
            episode_id: Bazarr episode ID
            subtitle_id: Subtitle provider ID
            language: Language code

        Returns:
            Download result
        """
        data = {
            "episodeid": episode_id,
            "subtitleid": subtitle_id,
            "language": language,
        }
        return await self._post("api/episodes/subtitles", data=data)

    async def download_movie_subtitle(
        self, movie_id: int, subtitle_id: str, language: str
    ) -> Dict[str, Any]:
        """Download a subtitle for a movie.

        Args:
            movie_id: Bazarr movie ID
            subtitle_id: Subtitle provider ID
            language: Language code

        Returns:
            Download result
        """
        data = {
            "movieid": movie_id,
            "subtitleid": subtitle_id,
            "language": language,
        }
        return await self._post("api/movies/subtitles", data=data)

    async def get_languages(self) -> List[Dict[str, Any]]:
        """Get available subtitle languages configured in Bazarr.

        Returns:
            List of configured languages
        """
        status = await self.get_system_status()
        # Extract languages from settings
        return status.get("data", {}).get("settings", {}).get("languages", [])

    async def sync_with_sonarr(self) -> Dict[str, Any]:
        """Trigger a sync with Sonarr to update episode list.

        Returns:
            Sync command result
        """
        return await self._post("api/system/tasks", data={"taskid": "update_series"})

    async def sync_with_radarr(self) -> Dict[str, Any]:
        """Trigger a sync with Radarr to update movie list.

        Returns:
            Sync command result
        """
        return await self._post("api/system/tasks", data={"taskid": "update_movies"})

    async def get_subtitle_history(
        self, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent subtitle download history.

        Args:
            limit: Maximum number of history entries to return

        Returns:
            List of recent subtitle downloads
        """
        return await self._get("api/history", params={"length": limit})
