"""Radarr API client implementation."""

from typing import Any, Dict, List

from .base import BaseMediaClient


class RadarrClient(BaseMediaClient):
    """Client for Radarr v3 API."""

    async def test_connection(self) -> bool:
        """Test connection to Radarr.

        Returns:
            True if connection successful
        """
        try:
            await self.get_system_status()
            return True
        except Exception:
            return False

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search for movies.

        Args:
            query: Movie title to search for

        Returns:
            List of matching movies from lookup
        """
        return await self._get("api/v3/movie/lookup", params={"term": query})

    async def get_item(self, item_id: int) -> Dict[str, Any]:
        """Get movie details by ID.

        Args:
            item_id: Movie ID

        Returns:
            Movie details
        """
        return await self._get(f"api/v3/movie/{item_id}")

    async def delete_item(self, item_id: int, delete_files: bool = False) -> bool:
        """Delete a movie.

        Args:
            item_id: Movie ID
            delete_files: Whether to delete all files

        Returns:
            True if successful
        """
        params = {"deleteFiles": str(delete_files).lower()}
        await self._delete(f"api/v3/movie/{item_id}?{'&'.join(f'{k}={v}' for k, v in params.items())}")
        return True

    async def get_all_movies(self) -> List[Dict[str, Any]]:
        """Get all movies in the library.

        Returns:
            List of all movies
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
        """Add a new movie to the library.

        Args:
            tmdb_id: TMDB ID of the movie
            title: Movie title
            quality_profile_id: Quality profile ID
            root_folder_path: Root folder path
            monitored: Whether to monitor the movie
            search_for_movie: Whether to search for the movie

        Returns:
            Added movie details
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
        """Get movie file details.

        Args:
            movie_id: Movie ID

        Returns:
            Movie file details
        """
        files = await self._get("api/v3/moviefile", params={"movieId": movie_id})
        return files[0] if files else {}

    async def delete_movie_file(self, file_id: int) -> bool:
        """Delete a movie file.

        Args:
            file_id: Movie file ID

        Returns:
            True if successful
        """
        await self._delete(f"api/v3/moviefile/{file_id}")
        return True

    async def trigger_movie_search(self, movie_id: int) -> Dict[str, Any]:
        """Trigger a search for a movie.

        Args:
            movie_id: Movie ID

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
