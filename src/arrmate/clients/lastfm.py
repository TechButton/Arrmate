"""Last.fm API client for music discovery.

Requires a free Last.fm API key: https://www.last.fm/api/account/create
Set LASTFM_API_KEY in your environment.
"""

from typing import Any, Dict, List, Optional

import httpx


class LastFMClient:
    """Client for the Last.fm v2 API (read-only chart/discovery endpoints)."""

    BASE_URL = "http://ws.audioscrobbler.com/2.0/"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _get(self, method: str, extra: Optional[Dict[str, Any]] = None) -> Any:
        params: Dict[str, Any] = {
            "method": method,
            "api_key": self.api_key,
            "format": "json",
            "limit": 24,
        }
        if extra:
            params.update(extra)
        resp = await self.client.get(self.BASE_URL, params=params)
        resp.raise_for_status()
        return resp.json()

    def _image_url(self, images: list) -> Optional[str]:
        """Return the largest non-empty image URL from a Last.fm image list."""
        for size in ("extralarge", "large", "medium", "small"):
            for img in images:
                if img.get("size") == size and img.get("#text"):
                    return img["#text"]
        return None

    async def get_top_artists(self) -> List[Dict[str, Any]]:
        """Global top artists chart."""
        data = await self._get("chart.gettopartists")
        raw = data.get("artists", {}).get("artist", [])
        return [
            {
                "display_title": a["name"],
                "artist": a["name"],
                "listeners": _fmt_listeners(a.get("listeners", "")),
                "poster": self._image_url(a.get("image", [])),
                "url": a.get("url", ""),
                "mbid": a.get("mbid", ""),
                "media_type": "music",
                "year": "",
                "overview": f"{_fmt_listeners(a.get('listeners', ''))} listeners",
            }
            for a in raw
        ]

    async def get_top_tracks(self) -> List[Dict[str, Any]]:
        """Global top tracks chart."""
        data = await self._get("chart.gettoptracks")
        raw = data.get("tracks", {}).get("track", [])
        return [
            {
                "display_title": t["name"],
                "artist": t.get("artist", {}).get("name", ""),
                "listeners": _fmt_listeners(t.get("listeners", "")),
                "poster": self._image_url(t.get("image", [])),
                "url": t.get("url", ""),
                "media_type": "music",
                "year": "",
                "overview": (
                    f"by {t.get('artist', {}).get('name', '')} · "
                    f"{_fmt_listeners(t.get('listeners', ''))} listeners"
                ),
            }
            for t in raw
        ]


def _fmt_listeners(raw: str) -> str:
    """Format a raw listener count string, e.g. '5234567' → '5.2M'."""
    try:
        n = int(raw)
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n // 1_000}K"
        return str(n)
    except (ValueError, TypeError):
        return raw
