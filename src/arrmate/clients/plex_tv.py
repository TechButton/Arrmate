"""Plex.tv API client for user/sharing management.

This talks to plex.tv (not the local Plex Media Server).
Used for inviting friends, listing existing shares, and revoking access.
All calls require a valid X-Plex-Token from the server owner's account.
"""

from typing import Any, Dict, List, Optional

import httpx


PLEX_TV = "https://plex.tv"

_HEADERS = {
    "X-Plex-Product": "Arrmate",
    "X-Plex-Client-Identifier": "arrmate-server-share",
    "Accept": "application/json",
}


class PlexTVClient:
    """Client for plex.tv user/sharing API."""

    def __init__(self, token: str, timeout: int = 20) -> None:
        self.token = token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={**_HEADERS, "X-Plex-Token": self.token},
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_friends(self) -> List[Dict[str, Any]]:
        """Return all plex.tv friends (users who have been shared any server).

        Each dict contains: id, username, title, email, thumb, servers[].
        """
        resp = await self.client.get(f"{PLEX_TV}/api/v2/friends")
        resp.raise_for_status()
        return resp.json()

    async def share_server(
        self,
        machine_identifier: str,
        invited_email: str,
        library_section_ids: List[int],
    ) -> Dict[str, Any]:
        """Invite a user by email and share selected library sections.

        Args:
            machine_identifier: Server machineIdentifier from /identity.
            invited_email: plex.tv email of the user to invite.
            library_section_ids: List of integer section keys to share.
                                 Empty list = share all libraries.

        Returns:
            Response dict from plex.tv (shared_server object).

        Raises:
            httpx.HTTPStatusError: On API error (e.g. 400 already shared,
                                   422 invalid email, 401 bad token).
        """
        resp = await self.client.post(
            f"{PLEX_TV}/api/v2/shared_servers",
            json={
                "machineIdentifier": machine_identifier,
                "invitedEmail": invited_email,
                "librarySectionIds": library_section_ids,
            },
        )
        resp.raise_for_status()
        return resp.json() if resp.text.strip() else {}

    async def remove_friend(self, friend_id: int) -> bool:
        """Revoke a friend's access to all your shared servers.

        Args:
            friend_id: The numeric id from get_friends().

        Returns:
            True on success.
        """
        resp = await self.client.delete(f"{PLEX_TV}/api/v2/friends/{friend_id}")
        return resp.status_code in (200, 204)
