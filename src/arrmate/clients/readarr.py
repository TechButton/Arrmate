"""Readarr API client implementation.

WARNING: Readarr project is officially retired as of 2026.
Support provided for existing instances only. Consider alternatives:
- Calibre-Web for eBooks
- LazyLibrarian for books and audiobooks
"""

import logging
from typing import Any, Dict, List

from .base import BaseMediaClient

logger = logging.getLogger(__name__)

DEPRECATION_WARNING = (
    "Readarr project is officially retired. "
    "Support provided for existing instances only. "
    "Consider migrating to Calibre-Web or LazyLibrarian."
)


class ReadarrClient(BaseMediaClient):
    """Client for Readarr v1 API (Books/Audiobooks).

    WARNING: Readarr project is deprecated. This client is provided
    for compatibility with existing instances only.
    """

    def __init__(self, base_url: str, api_key: str, timeout: int = 30) -> None:
        """Initialize the Readarr client.

        Args:
            base_url: Base URL of the Readarr service
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        super().__init__(base_url, api_key, timeout)
        logger.warning(f"Readarr client initialized - {DEPRECATION_WARNING}")

    async def test_connection(self) -> bool:
        """Test connection to Readarr.

        Returns:
            True if connection successful
        """
        try:
            # Readarr uses v1 API
            status = await self._get("api/v1/system/status")
            return bool(status)
        except Exception:
            return False

    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status and version.

        Note: Readarr uses v1 API instead of v3.

        Returns:
            System status information
        """
        return await self._get("api/v1/system/status")

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search for books/audiobooks.

        Args:
            query: Book title or author to search for

        Returns:
            List of matching books from lookup
        """
        return await self._get("api/v1/search", params={"term": query})

    async def get_item(self, item_id: int) -> Dict[str, Any]:
        """Get book/author details by ID.

        Args:
            item_id: Author ID

        Returns:
            Author details
        """
        return await self._get(f"api/v1/author/{item_id}")

    async def delete_item(self, item_id: int, delete_files: bool = False) -> bool:
        """Delete an author.

        Args:
            item_id: Author ID
            delete_files: Whether to delete all files

        Returns:
            True if successful
        """
        params = {"deleteFiles": str(delete_files).lower()}
        await self._delete(
            f"api/v1/author/{item_id}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
        )
        return True

    async def get_all_authors(self) -> List[Dict[str, Any]]:
        """Get all authors in the library.

        Returns:
            List of all authors
        """
        return await self._get("api/v1/author")

    async def add_author(
        self,
        foreign_author_id: str,
        author_name: str,
        quality_profile_id: int,
        metadata_profile_id: int,
        root_folder_path: str,
        monitored: bool = True,
        search_for_missing: bool = True,
    ) -> Dict[str, Any]:
        """Add a new author to the library.

        Args:
            foreign_author_id: GoodReads Author ID
            author_name: Author name
            quality_profile_id: Quality profile ID
            metadata_profile_id: Metadata profile ID
            root_folder_path: Root folder path
            monitored: Whether to monitor the author
            search_for_missing: Whether to search for missing books

        Returns:
            Added author details
        """
        data = {
            "foreignAuthorId": foreign_author_id,
            "authorName": author_name,
            "qualityProfileId": quality_profile_id,
            "metadataProfileId": metadata_profile_id,
            "rootFolderPath": root_folder_path,
            "monitored": monitored,
            "addOptions": {"searchForMissingBooks": search_for_missing},
        }
        return await self._post("api/v1/author", data=data)

    async def get_books(self, author_id: int) -> List[Dict[str, Any]]:
        """Get books for an author.

        Args:
            author_id: Author ID

        Returns:
            List of books
        """
        return await self._get("api/v1/book", params={"authorId": author_id})

    async def get_book_files(self, author_id: int) -> List[Dict[str, Any]]:
        """Get book files for an author.

        Args:
            author_id: Author ID

        Returns:
            List of book files
        """
        return await self._get("api/v1/bookfile", params={"authorId": author_id})

    async def delete_book_file(self, file_id: int) -> bool:
        """Delete a book file.

        Args:
            file_id: Book file ID

        Returns:
            True if successful
        """
        await self._delete(f"api/v1/bookfile/{file_id}")
        return True

    async def trigger_author_search(self, author_id: int) -> Dict[str, Any]:
        """Trigger a search for all missing books of an author.

        Args:
            author_id: Author ID

        Returns:
            Command response
        """
        return await self._post(
            "api/v1/command",
            data={"name": "AuthorSearch", "authorId": author_id},
        )

    async def trigger_book_search(self, book_ids: List[int]) -> Dict[str, Any]:
        """Trigger a search for specific books.

        Args:
            book_ids: List of book IDs

        Returns:
            Command response
        """
        return await self._post(
            "api/v1/command",
            data={"name": "BookSearch", "bookIds": book_ids},
        )

    async def get_quality_profiles(self) -> List[Dict[str, Any]]:
        """Get available quality profiles.

        Returns:
            List of quality profiles
        """
        return await self._get("api/v1/qualityprofile")

    async def get_metadata_profiles(self) -> List[Dict[str, Any]]:
        """Get available metadata profiles.

        Returns:
            List of metadata profiles
        """
        return await self._get("api/v1/metadataprofile")

    async def get_root_folders(self) -> List[Dict[str, Any]]:
        """Get available root folders.

        Returns:
            List of root folders
        """
        return await self._get("api/v1/rootfolder")
