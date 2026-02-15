"""Plex Media Server API client.

Plex is a media server/player, not a downloader or content manager.
It serves existing files and does NOT fit into the executor routing path.
This client provides read-heavy operations (list, search, refresh) with
limited write operations (delete to trash, scan, mark watched/unwatched).
"""

from typing import Any, Dict, List, Optional

import httpx

from .base_external import BaseExternalService


class PlexClient(BaseExternalService):
    """Client for interacting with the Plex Media Server API.

    Uses X-Plex-Token authentication instead of X-Api-Key.
    Requests JSON responses via Accept header (Plex defaults to XML).
    """

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client with Plex-specific headers."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "X-Plex-Token": self.api_key,
                    "X-Plex-Product": "Arrmate",
                    "X-Plex-Client-Identifier": "arrmate",
                    "Accept": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    async def test_connection(self) -> bool:
        """Test connection to Plex by fetching server identity.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            data = await self._get("/identity")
            return bool(data)
        except Exception:
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get library statistics (library count and section info).

        Returns:
            Dictionary with library stats
        """
        data = await self._get("/library/sections")
        sections = data.get("MediaContainer", {}).get("Directory", [])
        return {
            "library_count": len(sections),
            "libraries": [
                {"key": s.get("key"), "title": s.get("title"), "type": s.get("type")}
                for s in sections
            ],
        }

    async def get_version(self) -> Optional[str]:
        """Get server version from identity endpoint.

        Returns:
            Version string or None
        """
        try:
            data = await self._get("/identity")
            return data.get("MediaContainer", {}).get("version")
        except Exception:
            return None

    async def get_libraries(self) -> List[Dict[str, Any]]:
        """Get all library sections.

        Returns:
            List of library section dictionaries
        """
        data = await self._get("/library/sections")
        return data.get("MediaContainer", {}).get("Directory", [])

    async def get_library_items(
        self, section_id: str, libtype: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all items in a library section.

        Args:
            section_id: Library section key
            libtype: Filter by item type (e.g. 'movie', 'show', 'episode')

        Returns:
            List of media item dictionaries
        """
        params: Dict[str, Any] = {}
        if libtype:
            params["type"] = libtype
        data = await self._get(f"/library/sections/{section_id}/all", params=params)
        return data.get("MediaContainer", {}).get("Metadata", [])

    async def search(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Search across all libraries.

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of search result hub dictionaries
        """
        params = {"query": query, "limit": limit}
        data = await self._get("/hubs/search/", params=params)
        return data.get("MediaContainer", {}).get("Hub", [])

    async def get_item(self, rating_key: str) -> Dict[str, Any]:
        """Get details for a specific media item.

        Args:
            rating_key: Plex ratingKey identifier

        Returns:
            Media item metadata dictionary
        """
        data = await self._get(f"/library/metadata/{rating_key}")
        items = data.get("MediaContainer", {}).get("Metadata", [])
        return items[0] if items else {}

    async def refresh_metadata(self, rating_key: str) -> bool:
        """Refresh metadata for a specific item.

        Args:
            rating_key: Plex ratingKey identifier

        Returns:
            True if request was accepted
        """
        try:
            url = f"{self.base_url}/library/metadata/{rating_key}/refresh"
            response = await self.client.put(url)
            return response.status_code in (200, 204)
        except Exception:
            return False

    async def scan_library(self, section_id: str) -> bool:
        """Trigger a scan/refresh of a library section.

        Args:
            section_id: Library section key

        Returns:
            True if request was accepted
        """
        try:
            url = f"{self.base_url}/library/sections/{section_id}/refresh"
            response = await self.client.get(url)
            return response.status_code in (200, 204)
        except Exception:
            return False

    async def scan_all_libraries(self) -> bool:
        """Trigger a scan of all library sections.

        Returns:
            True if request was accepted
        """
        try:
            url = f"{self.base_url}/library/sections/all/refresh"
            response = await self.client.get(url)
            return response.status_code in (200, 204)
        except Exception:
            return False

    async def delete_item(self, rating_key: str) -> bool:
        """Delete a media item (sends to trash).

        Args:
            rating_key: Plex ratingKey identifier

        Returns:
            True if deletion was accepted
        """
        try:
            url = f"{self.base_url}/library/metadata/{rating_key}"
            response = await self.client.delete(url)
            return response.status_code in (200, 204)
        except Exception:
            return False

    async def empty_trash(self, section_id: str) -> bool:
        """Permanently delete items in a section's trash.

        Args:
            section_id: Library section key

        Returns:
            True if request was accepted
        """
        try:
            url = f"{self.base_url}/library/sections/{section_id}/emptyTrash"
            response = await self.client.put(url)
            return response.status_code in (200, 204)
        except Exception:
            return False

    async def get_sessions(self) -> List[Dict[str, Any]]:
        """Get all active streaming sessions.

        Returns:
            List of active session dictionaries
        """
        data = await self._get("/status/sessions")
        return data.get("MediaContainer", {}).get("Metadata", [])

    async def mark_watched(self, rating_key: str) -> bool:
        """Mark a media item as watched.

        Args:
            rating_key: Plex ratingKey identifier

        Returns:
            True if request was accepted
        """
        try:
            params = {
                "key": rating_key,
                "identifier": "com.plexapp.plugins.library",
            }
            url = f"{self.base_url}/:/scrobble"
            response = await self.client.get(url, params=params)
            return response.status_code in (200, 204)
        except Exception:
            return False

    async def mark_unwatched(self, rating_key: str) -> bool:
        """Mark a media item as unwatched.

        Args:
            rating_key: Plex ratingKey identifier

        Returns:
            True if request was accepted
        """
        try:
            params = {
                "key": rating_key,
                "identifier": "com.plexapp.plugins.library",
            }
            url = f"{self.base_url}/:/unscrobble"
            response = await self.client.get(url, params=params)
            return response.status_code in (200, 204)
        except Exception:
            return False
