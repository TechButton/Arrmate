"""Open Library API client for book discovery.

Open Library is free and requires no API key.
https://openlibrary.org/developers/api
"""

from typing import Any, Dict, List, Optional

import httpx


class OpenLibraryClient:
    """Client for the Open Library REST API."""

    BASE_URL = "https://openlibrary.org"
    COVER_BASE = "https://covers.openlibrary.org/b/id"

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=15,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        resp = await self.client.get(url, params=params or {})
        resp.raise_for_status()
        return resp.json()

    def cover_url(self, cover_id: int | None, size: str = "M") -> Optional[str]:
        """Return full cover image URL for a given Open Library cover ID."""
        if not cover_id:
            return None
        return f"{self.COVER_BASE}/{cover_id}-{size}.jpg"

    def _norm_trending(self, work: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise a trending/works entry into a common card dict."""
        authors = work.get("author_name") or []
        year = work.get("first_publish_year")
        cover_id = work.get("cover_i")
        subjects = work.get("subject", [])
        return {
            "display_title": work.get("title", "Unknown"),
            "author": ", ".join(authors[:2]),
            "year": str(year) if year else "",
            "poster": self.cover_url(cover_id),
            "overview": ", ".join(subjects[:3]) if subjects else "",
            "ol_key": work.get("key", ""),
            "media_type": "book",
        }

    def _norm_subject(self, work: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise a subject/works entry (slightly different schema)."""
        authors = work.get("authors") or []
        author_names = [a.get("name", "") for a in authors]
        year = work.get("first_publish_year")
        cover_id = work.get("cover_id")
        return {
            "display_title": work.get("title", "Unknown"),
            "author": ", ".join(author_names[:2]),
            "year": str(year) if year else "",
            "poster": self.cover_url(cover_id),
            "overview": "",
            "ol_key": (work.get("key") or ""),
            "media_type": "book",
        }

    async def get_trending_daily(self) -> List[Dict[str, Any]]:
        """Books trending today on Open Library."""
        data = await self._get("trending/daily.json", {"limit": 24})
        return [self._norm_trending(w) for w in data.get("works", [])]

    async def get_trending_weekly(self) -> List[Dict[str, Any]]:
        """Books trending this week on Open Library."""
        data = await self._get("trending/weekly.json", {"limit": 24})
        return [self._norm_trending(w) for w in data.get("works", [])]

    async def get_subject(self, subject: str) -> List[Dict[str, Any]]:
        """Top books for a genre/subject (e.g. 'fiction', 'mystery')."""
        data = await self._get(f"subjects/{subject}.json", {"limit": 24})
        return [self._norm_subject(w) for w in data.get("works", [])]
