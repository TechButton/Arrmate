"""LazyLibrarian API client implementation.

LazyLibrarian is an automated book and audiobook manager similar to
Sonarr/Radarr, with support for NZB/torrent downloads, Goodreads/GoogleBooks
metadata, and Calibre integration.
"""

from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from .base import BaseMediaClient


class LazyLibrarianClient(BaseMediaClient):
    """Client for LazyLibrarian API (Books & Audiobooks).

    LazyLibrarian provides automated downloading and management of
    books and audiobooks with Goodreads/GoogleBooks integration.
    """

    async def test_connection(self) -> bool:
        """Test connection to LazyLibrarian.

        Returns:
            True if connection successful
        """
        try:
            await self._api_call("getVersion")
            return True
        except Exception:
            return False

    async def _api_call(
        self, cmd: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Make a LazyLibrarian API call.

        LazyLibrarian uses ?cmd= style API with API key parameter.

        Args:
            cmd: Command name
            params: Additional parameters

        Returns:
            API response data
        """
        call_params = {"apikey": self.api_key, "cmd": cmd}
        if params:
            # URL encode parameters properly
            for key, value in params.items():
                if isinstance(value, str):
                    call_params[key] = quote_plus(value)
                else:
                    call_params[key] = value

        result = await self._get("api", params=call_params)

        # LazyLibrarian returns results in different formats
        # Simple commands return "OK", complex ones return data
        if isinstance(result, dict):
            return result
        return result

    async def get_system_status(self) -> Dict[str, Any]:
        """Get system version.

        Returns:
            Version information
        """
        version = await self._api_call("getVersion")
        return {"version": version}

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search for books or authors.

        Args:
            query: Book title or author name

        Returns:
            List of search results
        """
        result = await self._api_call("searchItem", {"item": query})
        # Return results if available, otherwise empty list
        if isinstance(result, dict):
            return result.get("results", [])
        return []

    async def find_author(self, name: str) -> List[Dict[str, Any]]:
        """Search for an author on GoodReads/GoogleBooks.

        Args:
            name: Author name

        Returns:
            List of matching authors
        """
        result = await self._api_call("findAuthor", {"name": name})
        if isinstance(result, dict):
            return result.get("results", [])
        return []

    async def find_book(self, name: str) -> List[Dict[str, Any]]:
        """Search for a book on GoodReads/GoogleBooks.

        Args:
            name: Book title

        Returns:
            List of matching books
        """
        result = await self._api_call("findBook", {"name": name})
        if isinstance(result, dict):
            return result.get("results", [])
        return []

    async def add_author(self, name: str) -> Dict[str, Any]:
        """Add an author to the database.

        Args:
            name: Author name

        Returns:
            Result of add operation
        """
        return await self._api_call("addAuthor", {"name": name})

    async def add_author_by_id(self, author_id: str) -> Dict[str, Any]:
        """Add an author by their AuthorID.

        Args:
            author_id: GoodReads/GoogleBooks author ID

        Returns:
            Result of add operation
        """
        return await self._api_call("addAuthorID", {"id": author_id})

    async def get_author(self, author_id: str) -> Dict[str, Any]:
        """Get author details and their books.

        Args:
            author_id: Author ID

        Returns:
            Author details with books
        """
        result = await self._api_call("getAuthor", {"id": author_id})
        if isinstance(result, dict):
            return result
        return {}

    async def get_item(self, item_id: int) -> Dict[str, Any]:
        """Get author details by ID.

        Args:
            item_id: Author ID

        Returns:
            Author details
        """
        return await self.get_author(str(item_id))

    async def delete_item(self, item_id: int, delete_files: bool = False) -> bool:
        """Delete an author.

        Args:
            item_id: Author ID
            delete_files: LazyLibrarian doesn't support this parameter

        Returns:
            True if successful
        """
        result = await self._api_call("removeAuthor", {"id": str(item_id)})
        return result == "OK" or (isinstance(result, dict) and result.get("success"))

    async def pause_author(self, author_id: str) -> Dict[str, Any]:
        """Pause author monitoring.

        Args:
            author_id: Author ID

        Returns:
            Result
        """
        return await self._api_call("pauseAuthor", {"id": author_id})

    async def resume_author(self, author_id: str) -> Dict[str, Any]:
        """Resume author monitoring.

        Args:
            author_id: Author ID

        Returns:
            Result
        """
        return await self._api_call("resumeAuthor", {"id": author_id})

    async def refresh_author(self, name: str, refresh: bool = True) -> Dict[str, Any]:
        """Refresh author data from GoodReads/GoogleBooks.

        Args:
            name: Author name
            refresh: Force refresh even if recently updated

        Returns:
            Result
        """
        params = {"name": name}
        if refresh:
            params["refresh"] = "1"
        return await self._api_call("refreshAuthor", params)

    async def get_all_books(self) -> List[Dict[str, Any]]:
        """Get all books in the database.

        Returns:
            List of all books
        """
        result = await self._api_call("getAllBooks")
        if isinstance(result, dict):
            return result.get("books", [])
        return []

    async def get_all_authors(self) -> List[Dict[str, Any]]:
        """Get all authors (index).

        Returns:
            List of all authors
        """
        result = await self._api_call("getIndex")
        if isinstance(result, dict):
            return result.get("authors", [])
        return []

    async def add_book(self, book_id: str) -> Dict[str, Any]:
        """Add a book to the database.

        Args:
            book_id: Book ID

        Returns:
            Result
        """
        return await self._api_call("addBook", {"id": book_id})

    async def queue_book(
        self, book_id: Optional[str] = None, book_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Mark a book as wanted.

        Args:
            book_id: Book ID
            book_type: Type (eBook or AudioBook)

        Returns:
            Result
        """
        params = {}
        if book_id:
            params["id"] = book_id
        if book_type:
            params["type"] = book_type
        return await self._api_call("queueBook", params)

    async def unqueue_book(
        self, book_id: Optional[str] = None, book_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Mark a book as skipped.

        Args:
            book_id: Book ID
            book_type: Type (eBook or AudioBook)

        Returns:
            Result
        """
        params = {}
        if book_id:
            params["id"] = book_id
        if book_type:
            params["type"] = book_type
        return await self._api_call("unqueueBook", params)

    async def search_book(
        self, book_id: str, book_type: Optional[str] = None, wait: bool = False
    ) -> Dict[str, Any]:
        """Search for a specific book by ID.

        Args:
            book_id: Book ID
            book_type: Type (eBook or AudioBook)
            wait: Wait for completion

        Returns:
            Search result
        """
        params = {"id": book_id}
        if book_type:
            params["type"] = book_type
        if wait:
            params["wait"] = "1"
        return await self._api_call("searchBook", params)

    async def force_library_scan(
        self, wait: bool = False, remove: bool = False, directory: Optional[str] = None
    ) -> Dict[str, Any]:
        """Force a library scan.

        Args:
            wait: Wait for completion
            remove: Remove missing books
            directory: Specific directory to scan

        Returns:
            Scan result
        """
        params = {}
        if wait:
            params["wait"] = "1"
        if remove:
            params["remove"] = "1"
        if directory:
            params["dir"] = directory
        return await self._api_call("forceLibraryScan", params)

    async def force_audiobook_scan(self, wait: bool = False) -> Dict[str, Any]:
        """Force an audiobook library scan.

        Args:
            wait: Wait for completion

        Returns:
            Scan result
        """
        params = {}
        if wait:
            params["wait"] = "1"
        return await self._api_call("forceAudioBookScan", params)

    async def get_magazines(self) -> List[Dict[str, Any]]:
        """Get all magazines.

        Returns:
            List of magazines
        """
        result = await self._api_call("getMagazines")
        if isinstance(result, dict):
            return result.get("magazines", [])
        return []

    async def add_magazine(self, name: str) -> Dict[str, Any]:
        """Add a magazine.

        Args:
            name: Magazine name

        Returns:
            Result
        """
        return await self._api_call("addMagazine", {"name": name})

    async def get_issues(self, magazine_name: str) -> List[Dict[str, Any]]:
        """Get issues for a magazine.

        Args:
            magazine_name: Magazine name

        Returns:
            List of issues
        """
        result = await self._api_call("getIssues", {"name": magazine_name})
        if isinstance(result, dict):
            return result.get("issues", [])
        return []

    async def restart(self) -> Dict[str, Any]:
        """Restart LazyLibrarian.

        Returns:
            Result
        """
        return await self._api_call("restart")

    async def shutdown(self) -> Dict[str, Any]:
        """Shutdown LazyLibrarian.

        Returns:
            Result
        """
        return await self._api_call("shutdown")

    # Implement abstract methods from BaseMediaClient

    async def get_all_series(self) -> List[Dict[str, Any]]:
        """Get all authors (LazyLibrarian uses authors not series).

        Returns:
            List of all authors
        """
        return await self.get_all_authors()

    async def get_all_movies(self) -> List[Dict[str, Any]]:
        """Alias for get_all_authors."""
        return await self.get_all_authors()

    async def get_quality_profiles(self) -> List[Dict[str, Any]]:
        """LazyLibrarian doesn't have quality profiles.

        Returns:
            Empty list
        """
        return []

    async def get_root_folders(self) -> List[Dict[str, Any]]:
        """LazyLibrarian doesn't expose root folders via API.

        Returns:
            Empty list
        """
        return []
