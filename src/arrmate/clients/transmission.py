"""Transmission RPC client."""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Transmission status codes
TRANSMISSION_STATUS = {0: "Stopped", 1: "Check queued", 2: "Checking", 3: "DL queued",
                       4: "Downloading", 5: "Seed queued", 6: "Seeding"}


class TransmissionClient:
    """Client for the Transmission RPC API."""

    def __init__(
        self, base_url: str, username: str = "", password: str = "", timeout: int = 30
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self._session_id = ""
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            auth = (self.username, self.password) if self.username else None
            self._client = httpx.AsyncClient(auth=auth, timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _rpc(self, method: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}/transmission/rpc"
        payload = {"method": method, "arguments": arguments or {}}
        headers = {"X-Transmission-Session-Id": self._session_id}

        resp = await self.client.post(url, json=payload, headers=headers)

        if resp.status_code == 409:
            # Fetch the CSRF session token and retry
            self._session_id = resp.headers.get("X-Transmission-Session-Id", "")
            headers["X-Transmission-Session-Id"] = self._session_id
            resp = await self.client.post(url, json=payload, headers=headers)

        resp.raise_for_status()
        return resp.json()

    async def test_connection(self) -> bool:
        try:
            await self._rpc("session-get")
            return True
        except Exception:
            return False

    async def get_session(self) -> Dict[str, Any]:
        """Get session info including speed limits."""
        return await self._rpc("session-get")

    async def get_torrents(self) -> Dict[str, Any]:
        """Get list of all torrents with key fields."""
        return await self._rpc("torrent-get", {
            "fields": ["id", "name", "status", "rateDownload", "rateUpload",
                       "percentDone", "totalSize", "error", "errorString"]
        })

    async def pause_torrent(self, torrent_id: int) -> bool:
        try:
            await self._rpc("torrent-stop", {"ids": [torrent_id]})
            return True
        except Exception:
            return False

    async def resume_torrent(self, torrent_id: int) -> bool:
        try:
            await self._rpc("torrent-start", {"ids": [torrent_id]})
            return True
        except Exception:
            return False

    async def set_speed_limit_down(self, kbps: int) -> bool:
        """Set download speed limit in KB/s (0 = disable limit)."""
        try:
            await self._rpc("session-set", {
                "speed-limit-down": kbps,
                "speed-limit-down-enabled": kbps > 0,
            })
            return True
        except Exception:
            return False

    async def set_speed_limit_up(self, kbps: int) -> bool:
        """Set upload speed limit in KB/s (0 = disable limit)."""
        try:
            await self._rpc("session-set", {
                "speed-limit-up": kbps,
                "speed-limit-up-enabled": kbps > 0,
            })
            return True
        except Exception:
            return False

    async def delete_torrent(self, torrent_id: int, delete_local_data: bool = False) -> bool:
        try:
            await self._rpc("torrent-remove", {
                "ids": [torrent_id],
                "delete-local-data": delete_local_data,
            })
            return True
        except Exception:
            return False
