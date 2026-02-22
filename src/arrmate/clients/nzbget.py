"""NZBget JSON-RPC download manager client."""

import logging
from typing import Any, List, Optional

import httpx

logger = logging.getLogger(__name__)


class NZBgetClient:
    """Client for the NZBget JSON-RPC API."""

    def __init__(self, base_url: str, username: str, password: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                auth=(self.username, self.password),
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _rpc(self, method: str, params: Optional[List[Any]] = None) -> Any:
        url = f"{self.base_url}/jsonrpc"
        payload = {"method": method, "params": params or [], "id": 1}
        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def test_connection(self) -> bool:
        try:
            data = await self._rpc("version")
            return bool(data.get("result"))
        except Exception:
            return False

    async def get_status(self) -> Any:
        """Get download status including speed and pause state."""
        return await self._rpc("status")

    async def get_queue(self) -> Any:
        """Get the download queue (list of groups)."""
        return await self._rpc("listgroups", [0])

    async def pause(self) -> bool:
        try:
            result = await self._rpc("pausedownload")
            return result.get("result", False)
        except Exception:
            return False

    async def resume(self) -> bool:
        try:
            result = await self._rpc("resumedownload")
            return result.get("result", False)
        except Exception:
            return False

    async def set_speed_limit(self, kbps: int) -> bool:
        """Set download rate limit in KB/s (0 = unlimited)."""
        try:
            result = await self._rpc("rate", [kbps])
            return result.get("result", False)
        except Exception:
            return False

    async def delete_item(self, nzo_id: int) -> bool:
        try:
            result = await self._rpc("editqueue", ["GroupDelete", "", [nzo_id]])
            return result.get("result", False)
        except Exception:
            return False
