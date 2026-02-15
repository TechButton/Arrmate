"""AudioBookshelf API client implementation.

AudioBookshelf is a self-hosted audiobook and podcast server with
a modern web UI, mobile apps, and robust playback tracking.
"""

from typing import Any, Dict, List, Optional

from .base import BaseMediaClient


class AudioBookshelfClient(BaseMediaClient):
    """Client for AudioBookshelf API (Audiobooks & Podcasts).

    AudioBookshelf is a purpose-built audiobook server with advanced
    playback features, progress tracking, and multi-user support.
    """

    def __init__(self, base_url: str, api_key: str, timeout: int = 30) -> None:
        """Initialize the AudioBookshelf client.

        Args:
            base_url: Base URL of AudioBookshelf
            api_key: API token/key for authentication
            timeout: Request timeout in seconds
        """
        super().__init__(base_url, api_key, timeout)

    @property
    def client(self):
        """Get or create the HTTP client with Bearer token auth."""
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
        return self._client

    async def test_connection(self) -> bool:
        """Test connection to AudioBookshelf.

        Returns:
            True if connection successful
        """
        try:
            await self.get_libraries()
            return True
        except Exception:
            return False

    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status and version.

        Returns:
            System status information
        """
        # AudioBookshelf doesn't have a v3/system/status endpoint
        # Use /api/me to validate authorization and get basic info
        return await self._get("api/authorize")

    async def get_libraries(self) -> List[Dict[str, Any]]:
        """Get all accessible libraries.

        Returns:
            List of libraries
        """
        result = await self._get("api/libraries")
        return result.get("libraries", []) if isinstance(result, dict) else result

    async def get_library(self, library_id: str) -> Dict[str, Any]:
        """Get specific library details.

        Args:
            library_id: Library ID

        Returns:
            Library details
        """
        return await self._get(f"api/libraries/{library_id}")

    async def get_library_items(
        self,
        library_id: str,
        limit: int = 100,
        page: int = 0,
        sort: Optional[str] = None,
        filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get items from a library.

        Args:
            library_id: Library ID
            limit: Number of items per page
            page: Page number
            sort: Sort field (e.g., "media.metadata.title")
            filter: Filter string

        Returns:
            Paginated library items
        """
        params = {"limit": limit, "page": page}
        if sort:
            params["sort"] = sort
        if filter:
            params["filter"] = filter

        return await self._get(f"api/libraries/{library_id}/items", params=params)

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search for audiobooks across all libraries.

        Args:
            query: Search query

        Returns:
            List of matching audiobooks
        """
        # AudioBookshelf search returns results grouped by type
        result = await self._get("api/search/library", params={"q": query})
        # Extract book results
        if isinstance(result, dict):
            return result.get("book", [])
        return []

    async def get_item(self, item_id: str) -> Dict[str, Any]:
        """Get audiobook details by ID.

        Args:
            item_id: Item ID

        Returns:
            Audiobook details
        """
        return await self._get(f"api/items/{item_id}")

    async def delete_item(self, item_id: str, delete_files: bool = False) -> bool:
        """Delete an audiobook.

        Args:
            item_id: Item ID
            delete_files: Whether to delete files (AudioBookshelf always deletes files)

        Returns:
            True if successful
        """
        await self._delete(f"api/items/{item_id}")
        return True

    async def get_progress(self) -> List[Dict[str, Any]]:
        """Get user's listening progress for all items.

        Returns:
            List of progress entries
        """
        result = await self._get("api/me/progress")
        return result.get("libraryItems", []) if isinstance(result, dict) else result

    async def update_progress(
        self,
        item_id: str,
        current_time: float,
        duration: Optional[float] = None,
        is_finished: bool = False,
    ) -> Dict[str, Any]:
        """Update playback progress for an audiobook.

        Args:
            item_id: Item ID
            current_time: Current playback position in seconds
            duration: Total duration in seconds
            is_finished: Whether playback is complete

        Returns:
            Updated progress
        """
        data = {
            "currentTime": current_time,
            "isFinished": is_finished,
        }
        if duration:
            data["duration"] = duration

        return await self._post(f"api/me/progress/{item_id}", data=data)

    async def get_sessions(self) -> List[Dict[str, Any]]:
        """Get listening sessions.

        Returns:
            List of playback sessions
        """
        return await self._get("api/me/listening-sessions")

    async def get_personalized(self, library_id: str) -> Dict[str, Any]:
        """Get personalized recommendations for a library.

        Args:
            library_id: Library ID

        Returns:
            Personalized shelves and recommendations
        """
        return await self._get(f"api/libraries/{library_id}/personalized")

    async def get_series(self, library_id: str) -> List[Dict[str, Any]]:
        """Get series in a library.

        Args:
            library_id: Library ID

        Returns:
            List of series
        """
        result = await self._get(f"api/libraries/{library_id}/series")
        return result.get("results", []) if isinstance(result, dict) else result

    async def get_collections(self, library_id: str) -> List[Dict[str, Any]]:
        """Get collections in a library.

        Args:
            library_id: Library ID

        Returns:
            List of collections
        """
        result = await self._get(f"api/libraries/{library_id}/collections")
        return result.get("collections", []) if isinstance(result, dict) else result

    async def create_collection(
        self, library_id: str, name: str, book_ids: List[str]
    ) -> Dict[str, Any]:
        """Create a new collection.

        Args:
            library_id: Library ID
            name: Collection name
            book_ids: List of book IDs to include

        Returns:
            Created collection
        """
        data = {
            "libraryId": library_id,
            "name": name,
            "books": book_ids,
        }
        return await self._post("api/collections", data=data)

    async def scan_library(self, library_id: str) -> Dict[str, Any]:
        """Trigger a library scan.

        Args:
            library_id: Library ID

        Returns:
            Scan command result
        """
        return await self._post(f"api/libraries/{library_id}/scan")

    async def match_audiobook(self, item_id: str) -> Dict[str, Any]:
        """Match audiobook to metadata providers.

        Args:
            item_id: Item ID

        Returns:
            Match result
        """
        return await self._post(f"api/items/{item_id}/match")

    # Implement abstract methods from BaseMediaClient
    # These map AudioBookshelf-specific methods to the generic interface

    async def get_all_series(self) -> List[Dict[str, Any]]:
        """Get all audiobooks across all libraries.

        Returns:
            List of all audiobooks
        """
        libraries = await self.get_libraries()
        all_items = []
        for library in libraries:
            if library.get("mediaType") == "book":
                result = await self.get_library_items(library["id"], limit=1000)
                items = result.get("results", [])
                all_items.extend(items)
        return all_items

    async def get_all_movies(self) -> List[Dict[str, Any]]:
        """Alias for get_all_series (AudioBookshelf doesn't have movies)."""
        return await self.get_all_series()

    async def get_quality_profiles(self) -> List[Dict[str, Any]]:
        """AudioBookshelf doesn't have quality profiles.

        Returns:
            Empty list
        """
        return []

    async def get_root_folders(self) -> List[Dict[str, Any]]:
        """Get library folders.

        Returns:
            List of libraries as "root folders"
        """
        return await self.get_libraries()
