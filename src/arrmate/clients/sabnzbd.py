"""SABnzbd download manager client."""

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class SABnzbdClient:
    """Client for the SABnzbd HTTP API."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _api_url(self) -> str:
        url = self.base_url.rstrip("/")
        # Accept URLs that already include the path (e.g. http://host:8080/sabnzbd)
        if url.endswith("/api"):
            return url
        if url.endswith("/sabnzbd"):
            return f"{url}/api"
        # Default: bare host:port — SABnzbd Docker (linuxserver) uses /api at root
        return f"{url}/api"

    async def _get(self, mode: str, extra: Optional[Dict[str, Any]] = None) -> Any:
        params = {"apikey": self.api_key, "output": "json", "mode": mode}
        if extra:
            params.update(extra)
        resp = await self.client.get(self._api_url(), params=params)
        resp.raise_for_status()
        return resp.json()

    async def test_connection(self) -> bool:
        try:
            data = await self._get("version")
            return bool(data)
        except Exception:
            return False

    async def get_status(self) -> Dict[str, Any]:
        """Get server status including speed, disk space, and pause state."""
        return await self._get("fullstatus")

    async def get_queue(self) -> Dict[str, Any]:
        """Get the download queue."""
        return await self._get("queue")

    async def pause(self) -> bool:
        try:
            await self._get("pause")
            return True
        except Exception:
            return False

    async def resume(self) -> bool:
        try:
            await self._get("resume")
            return True
        except Exception:
            return False

    async def set_speed_limit(self, kbps: int) -> bool:
        """Set download speed limit in KB/s (0 = unlimited)."""
        try:
            value = f"{kbps}K" if kbps > 0 else "0"
            await self._get("config", {"section": "misc", "keyword": "bandwidth_limit", "value": value})
            return True
        except Exception:
            return False

    async def delete_item(self, nzo_id: str, delete_files: bool = False) -> bool:
        try:
            await self._get("queue", {
                "name": "delete", "value": nzo_id, "del_files": 1 if delete_files else 0
            })
            return True
        except Exception:
            return False

    async def set_priority(self, nzo_id: str, priority: int) -> bool:
        """Set item priority: -1=low, 0=normal, 1=high, 2=forced."""
        try:
            await self._get("queue", {"name": "priority", "value": nzo_id, "extra": priority})
            return True
        except Exception:
            return False

    async def move_item(self, nzo_id: str, new_slot: int) -> bool:
        """Move item to an absolute queue slot position."""
        try:
            await self._get("queue", {"name": "move", "value": nzo_id, "extra": new_slot})
            return True
        except Exception:
            return False

    async def pause_item(self, nzo_id: str) -> bool:
        """Pause a single queue item."""
        try:
            await self._get("queue", {"name": "pause", "value": nzo_id})
            return True
        except Exception:
            return False

    async def resume_item(self, nzo_id: str) -> bool:
        """Resume a single paused queue item."""
        try:
            await self._get("queue", {"name": "resume", "value": nzo_id})
            return True
        except Exception:
            return False

    async def add_url(self, url: str, priority: int = 0, category: str = "") -> bool:
        """Add an NZB by URL."""
        try:
            await self._get("addurl", {"name": url, "priority": priority, "cat": category})
            return True
        except Exception:
            return False
