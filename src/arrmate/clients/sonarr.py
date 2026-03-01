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

    async def monitor_all_seasons(self, series_id: int) -> Dict[str, Any]:
        """Set all seasons of a series to monitored and save.

        Args:
            series_id: Series ID

        Returns:
            Updated series dict
        """
        series = await self._get(f"api/v3/series/{series_id}")
        for season in series.get("seasons", []):
            if season.get("seasonNumber", 0) > 0:
                season["monitored"] = True
        return await self._put(f"api/v3/series/{series_id}", data=series)

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

    async def set_series_monitored(self, series_id: int, monitored: bool) -> Dict[str, Any]:
        """Update the monitored status of a series.

        Args:
            series_id: Series ID
            monitored: True to monitor, False to unmonitor

        Returns:
            Updated series dict
        """
        series = await self._get(f"api/v3/series/{series_id}")
        series["monitored"] = monitored
        return await self._put(f"api/v3/series/{series_id}", data=series)

    async def trigger_season_search(self, series_id: int, season_number: int) -> Dict[str, Any]:
        """Trigger a search for all episodes in a season.

        Args:
            series_id: Series ID
            season_number: Season number

        Returns:
            Command response
        """
        return await self._post(
            "api/v3/command",
            data={"name": "SeasonSearch", "seriesId": series_id, "seasonNumber": season_number},
        )

    async def get_calendar(
        self, start: str, end: str, include_series: bool = True
    ) -> List[Dict[str, Any]]:
        """Get episodes airing between start and end dates.

        Args:
            start: ISO date string e.g. "2024-01-01"
            end: ISO date string e.g. "2024-01-08"
            include_series: Embed series info in each episode

        Returns:
            List of episode dicts with optional nested series
        """
        params: Dict[str, Any] = {
            "start": start,
            "end": end,
            "includeSeries": str(include_series).lower(),
            "includeEpisodeFile": "false",
        }
        return await self._get("api/v3/calendar", params=params)

    async def get_queue(self, page_size: int = 50) -> Dict[str, Any]:
        """Get the current download queue.

        Args:
            page_size: Number of items to return

        Returns:
            Paginated queue response with records array
        """
        params: Dict[str, Any] = {
            "pageSize": page_size,
            "includeSeries": "true",
            "includeEpisode": "true",
        }
        return await self._get("api/v3/queue", params=params)

    async def get_history(self, page_size: int = 25) -> Dict[str, Any]:
        """Get recent download history.

        Args:
            page_size: Number of items to return

        Returns:
            Paginated history response
        """
        params: Dict[str, Any] = {
            "pageSize": page_size,
            "includeSeries": "true",
            "includeEpisode": "true",
            "sortKey": "date",
            "sortDirection": "descending",
        }
        return await self._get("api/v3/history", params=params)

    async def get_wanted_missing(self, page_size: int = 50) -> Dict[str, Any]:
        """Get monitored episodes that are missing (no file yet).

        Args:
            page_size: Number of items to return

        Returns:
            Paginated missing episodes response
        """
        params: Dict[str, Any] = {
            "pageSize": page_size,
            "includeSeries": "true",
            "sortKey": "airDateUtc",
            "sortDirection": "descending",
        }
        return await self._get("api/v3/wanted/missing", params=params)

    async def trigger_rename_series(self, series_id: int) -> Dict[str, Any]:
        """Trigger a rename of all files for a series.

        Args:
            series_id: Series ID

        Returns:
            Command response
        """
        files = await self.get_episode_files(series_id)
        file_ids = [f["id"] for f in files if f.get("id")]
        return await self._post(
            "api/v3/command",
            data={"name": "RenameFiles", "seriesId": series_id, "files": file_ids},
        )

    async def rescan_series(self, series_id: int) -> Dict[str, Any]:
        """Trigger a disk rescan for a series.

        Args:
            series_id: Series ID

        Returns:
            Command response
        """
        return await self._post(
            "api/v3/command",
            data={"name": "RescanSeries", "seriesId": series_id},
        )

    async def get_tags(self) -> List[Dict[str, Any]]:
        """Get all tags defined in Sonarr."""
        return await self._get("api/v3/tag")

    async def create_tag(self, label: str) -> Dict[str, Any]:
        """Create a new tag.

        Args:
            label: Tag name

        Returns:
            Created tag dict with id and label
        """
        return await self._post("api/v3/tag", data={"label": label})

    async def delete_tag(self, tag_id: int) -> bool:
        """Delete a tag.

        Args:
            tag_id: Tag ID to delete

        Returns:
            True if successful
        """
        await self._delete(f"api/v3/tag/{tag_id}")
        return True

    async def add_tag_to_series(self, series_id: int, tag_id: int) -> Dict[str, Any]:
        """Add a tag to a series (no-op if already present).

        Args:
            series_id: Series ID
            tag_id: Tag ID to add

        Returns:
            Updated series dict
        """
        series = await self._get(f"api/v3/series/{series_id}")
        existing = series.get("tags", [])
        if tag_id not in existing:
            series["tags"] = existing + [tag_id]
            return await self._put(f"api/v3/series/{series_id}", data=series)
        return series

    async def remove_tag_from_series(self, series_id: int, tag_id: int) -> Dict[str, Any]:
        """Remove a tag from a series.

        Args:
            series_id: Series ID
            tag_id: Tag ID to remove

        Returns:
            Updated series dict
        """
        series = await self._get(f"api/v3/series/{series_id}")
        series["tags"] = [t for t in series.get("tags", []) if t != tag_id]
        return await self._put(f"api/v3/series/{series_id}", data=series)
