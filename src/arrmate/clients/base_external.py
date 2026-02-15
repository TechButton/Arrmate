"""Base class for external service API clients.

External services are orchestration or monitoring tools that work across
multiple media services but don't manage media directly. Examples:
- huntarr.io (automation/orchestration)
- Overseerr (request management)
- Tautulli (Plex monitoring)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx


class BaseExternalService(ABC):
    """Abstract base class for external service clients.

    External services don't manage media items directly but provide
    orchestration, monitoring, or request management across other services.
    """

    def __init__(self, base_url: str, api_key: str, timeout: int = 30) -> None:
        """Initialize the external service client.

        Args:
            base_url: Base URL of the external service
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
        # Add API key to params if not in headers
        if params is None:
            params = {}
        if "apikey" not in params and "X-Api-Key" not in self.client.headers:
            params["apikey"] = self.api_key

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

    async def _put(
        self, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Make a PUT request.

        Args:
            endpoint: API endpoint
            data: Request body

        Returns:
            Response JSON data
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = await self.client.put(url, json=data)
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
        """Test connection to the external service.

        Returns:
            True if connection is successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics or dashboard metrics.

        Returns:
            Dictionary of statistics/metrics
        """
        pass
