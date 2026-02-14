"""Base class for media service API clients."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx


class BaseMediaClient(ABC):
    """Abstract base class for media service clients."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30) -> None:
        """Initialize the media client.

        Args:
            base_url: Base URL of the media service (e.g., http://sonarr:8989)
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"X-Api-Key": self.api_key},
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make a GET request.

        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters

        Returns:
            Response JSON data

        Raises:
            httpx.HTTPError: If request fails
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def _post(
        self, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Make a POST request.

        Args:
            endpoint: API endpoint
            data: Request body

        Returns:
            Response JSON data
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = await self.client.post(url, json=data)
        response.raise_for_status()
        return response.json()

    async def _delete(self, endpoint: str) -> Any:
        """Make a DELETE request.

        Args:
            endpoint: API endpoint

        Returns:
            Response JSON data
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = await self.client.delete(url)
        response.raise_for_status()
        return response.json() if response.text else None

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connection to the service.

        Returns:
            True if connection is successful, False otherwise
        """
        pass

    @abstractmethod
    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search for media items.

        Args:
            query: Search query (title, etc.)

        Returns:
            List of matching items
        """
        pass

    @abstractmethod
    async def get_item(self, item_id: int) -> Dict[str, Any]:
        """Get details of a specific media item.

        Args:
            item_id: Item ID

        Returns:
            Item details
        """
        pass

    @abstractmethod
    async def delete_item(self, item_id: int, delete_files: bool = False) -> bool:
        """Delete a media item.

        Args:
            item_id: Item ID
            delete_files: Whether to delete associated files

        Returns:
            True if successful
        """
        pass

    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status and version.

        Returns:
            System status information
        """
        return await self._get("api/v3/system/status")
