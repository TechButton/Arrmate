"""Base class for companion service API clients.

Companion services supplement primary media services (like Sonarr/Radarr)
rather than managing media directly. Examples include:
- Bazarr (subtitle management)
- Future services that enhance primary media managers
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx


class BaseCompanionClient(ABC):
    """Abstract base class for companion service clients.

    Companion services work alongside primary media services to provide
    additional functionality like subtitles, metadata, or monitoring.
    """

    def __init__(self, base_url: str, api_key: str, timeout: int = 30) -> None:
        """Initialize the companion client.

        Args:
            base_url: Base URL of the companion service
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
        """Test connection to the companion service.

        Returns:
            True if connection is successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_missing_items(self, service_type: str) -> List[Dict[str, Any]]:
        """Get items missing from the companion service.

        For example, Bazarr would return episodes/movies missing subtitles.

        Args:
            service_type: Type of primary service ("sonarr", "radarr", etc.)

        Returns:
            List of missing items
        """
        pass

    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status and version.

        Default implementation - can be overridden by subclasses.

        Returns:
            System status information
        """
        return await self._get("api/system/status")
