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

    async def get_machine_identifier(self) -> Optional[str]:
        """Get the server's unique machineIdentifier (needed for sharing via plex.tv).

        Returns:
            machineIdentifier string, or None on failure.
        """
        try:
            data = await self._get("/identity")
            return data.get("MediaContainer", {}).get("machineIdentifier")
        except Exception:
            return None

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

    async def get_accounts(self) -> List[Dict[str, Any]]:
        """Get list of server accounts/users.

        Returns:
            List of account dicts with id, name, thumb fields
        """
        try:
            data = await self._get("/accounts")
            return data.get("MediaContainer", {}).get("Account", [])
        except Exception:
            return []

    async def get_history(
        self,
        account_id: Optional[int] = None,
        limit: int = 50,
        min_date: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get playback history, optionally filtered by user account and date.

        Args:
            account_id: Filter by Plex account ID (from get_accounts). None = all users.
            limit: Maximum number of history items to return.
            min_date: Unix timestamp — only return items viewed after this time.

        Returns:
            List of history item dicts with viewedAt, title, type, user info
        """
        params: dict = {"X-Plex-Container-Size": limit, "sort": "viewedAt:desc"}
        if account_id:
            params["accountID"] = account_id
        if min_date:
            params["minDate"] = min_date
        data = await self._get("/status/sessions/history/all", params=params)
        return data.get("MediaContainer", {}).get("Metadata", [])

    async def get_continue_watching(self) -> List[Dict[str, Any]]:
        """Get items currently in progress (continue watching hub).

        Returns:
            List of in-progress media items with viewOffset
        """
        try:
            # /hubs/home/continueWatching returns Metadata directly (not Hub-wrapped)
            data = await self._get("/hubs/home/continueWatching")
            container = data.get("MediaContainer", {})
            items = container.get("Metadata", [])
            if items:
                return items
            # Fallback: /library/onDeck filtered to items with a viewOffset
            data2 = await self._get("/library/onDeck")
            all_deck = data2.get("MediaContainer", {}).get("Metadata", [])
            return [i for i in all_deck if i.get("viewOffset", 0) > 0]
        except Exception:
            return []

    async def get_on_deck(self) -> List[Dict[str, Any]]:
        """Get on-deck items (next episodes to watch for in-progress shows).

        Returns:
            List of on-deck media items
        """
        data = await self._get("/library/onDeck")
        return data.get("MediaContainer", {}).get("Metadata", [])

    async def get_recently_added(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Get recently added items across all libraries.

        Args:
            limit: Maximum number of items to return.

        Returns:
            List of recently added media items
        """
        params: dict = {"X-Plex-Container-Size": limit}
        data = await self._get("/library/recentlyAdded", params=params)
        return data.get("MediaContainer", {}).get("Metadata", [])

    async def terminate_session(
        self, session_id: str, reason: str = "Terminated by Arrmate"
    ) -> bool:
        """Terminate an active streaming session.

        Args:
            session_id: The Session.id UUID from get_sessions() (not sessionKey)
            reason: Message shown to the user on their player

        Returns:
            True if termination was accepted
        """
        try:
            url = f"{self.base_url}/status/sessions/terminate"
            response = await self.client.delete(
                url, params={"sessionId": session_id, "reason": reason}
            )
            return response.status_code in (200, 204)
        except Exception:
            return False

    async def rate_item(self, rating_key: str, stars: float) -> bool:
        """Rate a media item.

        Args:
            rating_key: Plex ratingKey identifier
            stars: Rating from 1-5 (converted to Plex's 2-10 internal scale)

        Returns:
            True if rating was accepted
        """
        try:
            params = {
                "key": rating_key,
                "identifier": "com.plexapp.plugins.library",
                "rating": int(max(1, min(5, stars)) * 2),
            }
            url = f"{self.base_url}/:/rate"
            response = await self.client.put(url, params=params)
            return response.status_code in (200, 204)
        except Exception:
            return False

    async def get_butler_tasks(self) -> List[Dict[str, Any]]:
        """Get available Butler maintenance tasks and their status.

        Returns:
            List of ButlerTask dicts with name, description, scheduleRandomized
        """
        try:
            data = await self._get("/butler")
            return data.get("MediaContainer", {}).get("ButlerTask", [])
        except Exception:
            return []

    async def run_butler_task(self, task_name: str) -> bool:
        """Run a specific Butler maintenance task immediately.

        Args:
            task_name: Task name (e.g. CleanOldBundles, BackupDatabase)

        Returns:
            True if the task was started
        """
        try:
            url = f"{self.base_url}/butler/{task_name}"
            response = await self.client.post(url)
            return response.status_code in (200, 204)
        except Exception:
            return False

    async def detect_intro(self, rating_key: str) -> bool:
        """Trigger media analysis for an item (queues intro/chapter marker detection).

        Args:
            rating_key: Plex ratingKey — can be a series, season, or episode

        Returns:
            True if analysis was queued
        """
        try:
            url = f"{self.base_url}/library/metadata/{rating_key}/analyze"
            response = await self.client.put(url)
            return response.status_code in (200, 204)
        except Exception:
            return False

    async def detect_credits(self, rating_key: str) -> bool:
        """Trigger media analysis for an item (queues end-credit marker detection).

        Uses the same /analyze endpoint as intro detection — Plex queues all
        marker types (intro, credits, chapter thumbnails) together.

        Args:
            rating_key: Plex ratingKey — can be a series, season, or episode

        Returns:
            True if analysis was queued
        """
        try:
            url = f"{self.base_url}/library/metadata/{rating_key}/analyze"
            response = await self.client.put(url)
            return response.status_code in (200, 204)
        except Exception:
            return False

    async def get_playlists(self) -> List[Dict[str, Any]]:
        """Get all playlists on this server.

        Returns:
            List of playlist dicts with ratingKey, title, playlistType, duration, leafCount
        """
        try:
            data = await self._get("/playlists/all")
            return data.get("MediaContainer", {}).get("Metadata", [])
        except Exception:
            return []

    async def get_playlist_items(self, playlist_id: str) -> List[Dict[str, Any]]:
        """Get items in a playlist.

        Args:
            playlist_id: Playlist ratingKey

        Returns:
            List of media item dicts
        """
        data = await self._get(f"/playlists/{playlist_id}/items")
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
