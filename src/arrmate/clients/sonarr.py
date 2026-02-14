"""Sonarr API client implementation."""

from typing import Any, Dict, List, Optional

from .base import BaseMediaClient


class SonarrClient(BaseMediaClient):
    """Client for Sonarr v3 API."""

    async def test_connection(self) -> bool:
        """Test connection to Sonarr.

        Returns:
            True if connection successful
        """
        try:
            await self.get_system_status()
            return True
        except Exception:
            return False

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search for TV shows.

        Args:
            query: Show title to search for

        Returns:
            List of matching shows from lookup
        """
        return await self._get("api/v3/series/lookup", params={"term": query})

    async def get_item(self, item_id: int) -> Dict[str, Any]:
        """Get series details by ID.

        Args:
            item_id: Series ID

        Returns:
            Series details
        """
        return await self._get(f"api/v3/series/{item_id}")

    async def delete_item(self, item_id: int, delete_files: bool = False) -> bool:
        """Delete a series.

        Args:
            item_id: Series ID
            delete_files: Whether to delete all files

        Returns:
            True if successful
        """
        params = {"deleteFiles": str(delete_files).lower()}
        await self._delete(f"api/v3/series/{item_id}?{'&'.join(f'{k}={v}' for k, v in params.items())}")
        return True

    async def get_all_series(self) -> List[Dict[str, Any]]:
        """Get all series in the library.

        Returns:
            List of all series
        """
        return await self._get("api/v3/series")

    async def add_series(
        self,
        tvdb_id: int,
        title: str,
        quality_profile_id: int,
        root_folder_path: str,
        monitored: bool = True,
        search_for_missing: bool = True,
    ) -> Dict[str, Any]:
        """Add a new series to the library.

        Args:
            tvdb_id: TVDB ID of the series
            title: Series title
            quality_profile_id: Quality profile ID
            root_folder_path: Root folder path
            monitored: Whether to monitor the series
            search_for_missing: Whether to search for missing episodes

        Returns:
            Added series details
        """
        data = {
            "tvdbId": tvdb_id,
            "title": title,
            "qualityProfileId": quality_profile_id,
            "rootFolderPath": root_folder_path,
            "monitored": monitored,
            "addOptions": {"searchForMissingEpisodes": search_for_missing},
        }
        return await self._post("api/v3/series", data=data)

    async def get_episodes(
        self, series_id: int, season_number: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get episodes for a series.

        Args:
            series_id: Series ID
            season_number: Optional season number filter

        Returns:
            List of episodes
        """
        params = {"seriesId": series_id}
        if season_number is not None:
            params["seasonNumber"] = season_number
        return await self._get("api/v3/episode", params=params)

    async def get_episode_files(self, series_id: int) -> List[Dict[str, Any]]:
        """Get episode files for a series.

        Args:
            series_id: Series ID

        Returns:
            List of episode files
        """
        return await self._get("api/v3/episodefile", params={"seriesId": series_id})

    async def delete_episode_file(self, file_id: int) -> bool:
        """Delete an episode file.

        Args:
            file_id: Episode file ID

        Returns:
            True if successful
        """
        await self._delete(f"api/v3/episodefile/{file_id}")
        return True

    async def delete_episode_files(self, file_ids: List[int]) -> int:
        """Delete multiple episode files.

        Args:
            file_ids: List of episode file IDs

        Returns:
            Number of files deleted
        """
        deleted = 0
        for file_id in file_ids:
            try:
                await self.delete_episode_file(file_id)
                deleted += 1
            except Exception:
                pass
        return deleted

    async def trigger_series_search(self, series_id: int) -> Dict[str, Any]:
        """Trigger a search for all missing episodes of a series.

        Args:
            series_id: Series ID

        Returns:
            Command response
        """
        return await self._post(
            "api/v3/command",
            data={"name": "SeriesSearch", "seriesId": series_id},
        )

    async def trigger_episode_search(self, episode_ids: List[int]) -> Dict[str, Any]:
        """Trigger a search for specific episodes.

        Args:
            episode_ids: List of episode IDs

        Returns:
            Command response
        """
        return await self._post(
            "api/v3/command",
            data={"name": "EpisodeSearch", "episodeIds": episode_ids},
        )

    async def get_quality_profiles(self) -> List[Dict[str, Any]]:
        """Get available quality profiles.

        Returns:
            List of quality profiles
        """
        return await self._get("api/v3/qualityprofile")

    async def get_root_folders(self) -> List[Dict[str, Any]]:
        """Get available root folders.

        Returns:
            List of root folders
        """
        return await self._get("api/v3/rootfolder")
