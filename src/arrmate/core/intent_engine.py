"""Intent validation and enrichment engine."""

from typing import Any, Dict, List, Optional

from ..clients.base import BaseMediaClient
from ..clients.discovery import get_client_for_media_type
from .models import Intent


class IntentEngine:
    """Validates and enriches Intent objects with additional context."""

    async def enrich(self, intent: Intent) -> Intent:
        """Enrich an intent with additional context.

        This includes:
        - Fuzzy matching titles to find exact IDs
        - Resolving season/episode references
        - Validating criteria

        Args:
            intent: The intent to enrich

        Returns:
            Enriched intent with additional fields populated

        Raises:
            ValueError: If required information cannot be resolved
        """
        # Get the appropriate client for this media type
        client = get_client_for_media_type(intent.media_type.value)

        try:
            # If we have a title, try to find the item in the service
            if intent.title and not intent.item_id:
                await self._resolve_title(intent, client)

            # For TV shows, resolve episode information
            if intent.media_type.value == "tv" and intent.series_id:
                await self._resolve_episodes(intent, client)

            return intent

        finally:
            await client.close()

    async def _resolve_title(self, intent: Intent, client: BaseMediaClient) -> None:
        """Resolve a title to an item ID using fuzzy matching.

        Args:
            intent: Intent to update
            client: Media client to use for lookup
        """
        # First, search in the library
        if hasattr(client, "get_all_series"):
            # TV show
            all_items = await client.get_all_series()
        elif hasattr(client, "get_all_movies"):
            # Movie
            all_items = await client.get_all_movies()
        else:
            all_items = []

        # Try exact match first
        for item in all_items:
            if item.get("title", "").lower() == intent.title.lower():
                intent.item_id = item.get("id")
                if intent.media_type.value == "tv":
                    intent.series_id = item.get("id")
                return

        # Try partial match
        for item in all_items:
            if intent.title.lower() in item.get("title", "").lower():
                intent.item_id = item.get("id")
                if intent.media_type.value == "tv":
                    intent.series_id = item.get("id")
                return

        # If not found in library, search external sources
        search_results = await client.search(intent.title)

        if not search_results:
            raise ValueError(f"Could not find '{intent.title}' in library or search results")

        # Use the first result
        first_result = search_results[0]

        # For items not in library, we may need to add them first
        # Store the search result for later use in executor
        if intent.media_type.value == "tv":
            intent.item_id = first_result.get("tvdbId")
        elif intent.media_type.value == "movie":
            intent.item_id = first_result.get("tmdbId")

    async def _resolve_episodes(self, intent: Intent, client: BaseMediaClient) -> None:
        """Resolve episode references for TV shows.

        Args:
            intent: Intent to update
            client: Sonarr client
        """
        if not intent.series_id:
            return

        # Get all episodes for the series
        all_episodes = await client.get_episodes(
            intent.series_id, season_number=intent.season
        )

        # Store episode details for later use
        if not hasattr(intent, "_episode_details"):
            intent._episode_details = all_episodes

    def validate(self, intent: Intent) -> List[str]:
        """Validate an intent and return any validation errors.

        Args:
            intent: Intent to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check required fields based on action
        if intent.action.value in ["remove", "delete", "info"]:
            if not intent.title:
                errors.append("Title is required for this action")

        if intent.action.value == "add":
            if not intent.title:
                errors.append("Title is required to add media")

        # TV-specific validation
        if intent.media_type.value == "tv":
            if intent.action.value in ["remove", "delete"]:
                if intent.episodes and not intent.season:
                    errors.append("Season number is required when specifying episodes")

        return errors
