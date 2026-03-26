"""ReadMeABook API client implementation.

ReadMeABook is a self-hosted audiobook library automation platform
that manages audiobook acquisition for Plex and AudioBookshelf.
It integrates with torrent/usenet download clients and provides
a request workflow for multi-user environments.

Default port: 3030
Auth: Bearer token (JWT from login or admin-generated API token)
"""

from typing import Any, Dict, List, Optional

from .base_external import BaseExternalService


class ReadMeABookClient(BaseExternalService):
    """Client for ReadMeABook REST API."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30) -> None:
        super().__init__(base_url, api_key, timeout)

    @property
    def client(self):
        """HTTP client with Bearer token auth."""
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def _post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = await self.client.post(url, json=data or {})
        response.raise_for_status()
        return response.json()

    async def test_connection(self) -> bool:
        """Test connection to ReadMeABook."""
        try:
            await self._get("api/health")
            return True
        except Exception:
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get ReadMeABook library statistics."""
        try:
            data = await self._get("api/stats")
            if isinstance(data, dict):
                return data
            return {}
        except Exception:
            return {}

    async def get_version(self) -> Optional[str]:
        """Get application version."""
        try:
            data = await self._get("api/version")
            if isinstance(data, dict):
                return data.get("version") or data.get("tag")
            return None
        except Exception:
            return None

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search audiobooks by title or author.

        Returns list of audiobook dicts with title, author, asin fields.
        """
        try:
            data = await self._get("api/audiobooks/search", params={"q": query})
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("results", data.get("audiobooks", data.get("books", [])))
            return []
        except Exception:
            return []

    async def get_popular(self) -> List[Dict[str, Any]]:
        """Get popular audiobooks."""
        try:
            data = await self._get("api/audiobooks/popular")
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("results", data.get("audiobooks", []))
            return []
        except Exception:
            return []

    async def get_new_releases(self) -> List[Dict[str, Any]]:
        """Get new audiobook releases."""
        try:
            data = await self._get("api/audiobooks/new-releases")
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("results", data.get("audiobooks", []))
            return []
        except Exception:
            return []

    async def get_requests(self) -> List[Dict[str, Any]]:
        """List all audiobook requests."""
        try:
            data = await self._get("api/requests")
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("requests", data.get("results", []))
            return []
        except Exception:
            return []

    async def create_request(
        self,
        asin: str,
        title: str,
        author: str = "",
    ) -> Dict[str, Any]:
        """Submit an audiobook request.

        Args:
            asin: Amazon ASIN for the audiobook
            title: Audiobook title
            author: Author name

        Returns:
            Created request details
        """
        payload: Dict[str, Any] = {"asin": asin, "title": title}
        if author:
            payload["author"] = author
        return await self._post("api/requests", data=payload)
