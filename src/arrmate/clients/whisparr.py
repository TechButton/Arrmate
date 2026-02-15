"""Whisparr API client implementation."""

from typing import Any, Dict, List

from .base import BaseMediaClient


class WhisparrClient(BaseMediaClient):
    """Client for Whisparr v3 API (Adult content).

    Note: Whisparr uses the same v3 API structure as Radarr,
    managing adult videos with TMDb metadata.
    """

    async def test_connection(self) -> bool:
        """Test connection to Whisparr.

        Returns:
            True if connection successful
        """
        try:
            await self.get_system_status()
            return True
        except Exception:
            return False

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search for adult content.

        Args:
            query: Title to search for

        Returns:
            List of matching items from lookup
        """
        return await self._get("api/v3/movie/lookup", params={"term": query})

    async def get_item(self, item_id: int) -> Dict[str, Any]:
        """Get item details by ID.

        Args:
            item_id: Item ID

        Returns:
            Item details
        """
        return await self._get(f"api/v3/movie/{item_id}")

    async def delete_item(self, item_id: int, delete_files: bool = False) -> bool:
        """Delete an item.

        Args:
            item_id: Item ID
            delete_files: Whether to delete all files

        Returns:
            True if successful
        """
        params = {"deleteFiles": str(delete_files).lower()}
        await self._delete(
            f"api/v3/movie/{item_id}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
        )
        return True

    async def get_all_movies(self) -> List[Dict[str, Any]]:
        """Get all items in the library.

        Returns:
            List of all items
        """
        return await self._get("api/v3/movie")

    async def add_movie(
        self,
        tmdb_id: int,
        title: str,
        quality_profile_id: int,
        root_folder_path: str,
        monitored: bool = True,
        search_for_movie: bool = True,
    ) -> Dict[str, Any]:
        """Add a new item to the library.

        Args:
            tmdb_id: TMDB ID
            title: Title
            quality_profile_id: Quality profile ID
            root_folder_path: Root folder path
            monitored: Whether to monitor the item
            search_for_movie: Whether to search for the item

        Returns:
            Added item details
        """
        data = {
            "tmdbId": tmdb_id,
            "title": title,
            "qualityProfileId": quality_profile_id,
            "rootFolderPath": root_folder_path,
            "monitored": monitored,
            "addOptions": {"searchForMovie": search_for_movie},
        }
        return await self._post("api/v3/movie", data=data)

    async def get_movie_file(self, movie_id: int) -> Dict[str, Any]:
        """Get file details for an item.

        Args:
            movie_id: Item ID

        Returns:
            File details
        """
        files = await self._get("api/v3/moviefile", params={"movieId": movie_id})
        return files[0] if files else {}

    async def delete_movie_file(self, file_id: int) -> bool:
        """Delete a file.

        Args:
            file_id: File ID

        Returns:
            True if successful
        """
        await self._delete(f"api/v3/moviefile/{file_id}")
        return True

    async def trigger_movie_search(self, movie_id: int) -> Dict[str, Any]:
        """Trigger a search for an item.

        Args:
            movie_id: Item ID

        Returns:
            Command response
        """
        return await self._post(
            "api/v3/command",
            data={"name": "MoviesSearch", "movieIds": [movie_id]},
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
