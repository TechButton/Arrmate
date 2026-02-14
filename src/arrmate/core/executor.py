"""Intent execution orchestrator."""

from typing import List

from ..clients.base import BaseMediaClient
from ..clients.discovery import get_client_for_media_type
from ..clients.radarr import RadarrClient
from ..clients.sonarr import SonarrClient
from .models import ActionType, ExecutionResult, Intent


class Executor:
    """Executes validated intents against media service APIs."""

    async def execute(self, intent: Intent) -> ExecutionResult:
        """Execute an intent and return the result.

        Args:
            intent: The intent to execute (should be enriched)

        Returns:
            ExecutionResult with success status and details
        """
        try:
            # Get the appropriate client
            client = get_client_for_media_type(intent.media_type.value)

            try:
                # Route to appropriate handler based on action
                if intent.action == ActionType.REMOVE or intent.action == ActionType.DELETE:
                    return await self._execute_remove(intent, client)
                elif intent.action == ActionType.SEARCH:
                    return await self._execute_search(intent, client)
                elif intent.action == ActionType.ADD:
                    return await self._execute_add(intent, client)
                elif intent.action == ActionType.LIST:
                    return await self._execute_list(intent, client)
                elif intent.action == ActionType.INFO:
                    return await self._execute_info(intent, client)
                else:
                    return ExecutionResult(
                        success=False,
                        message=f"Action '{intent.action}' not yet implemented",
                    )
            finally:
                await client.close()

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Execution failed: {str(e)}",
                errors=[str(e)],
            )

    async def _execute_remove(
        self, intent: Intent, client: BaseMediaClient
    ) -> ExecutionResult:
        """Execute a remove/delete action.

        Args:
            intent: Intent to execute
            client: Media client

        Returns:
            Execution result
        """
        if intent.media_type.value == "tv":
            return await self._remove_tv_content(intent, client)
        elif intent.media_type.value == "movie":
            return await self._remove_movie(intent, client)
        else:
            return ExecutionResult(
                success=False,
                message=f"Remove not yet implemented for {intent.media_type}",
            )

    async def _remove_tv_content(
        self, intent: Intent, client: SonarrClient
    ) -> ExecutionResult:
        """Remove TV show episodes or entire series.

        Args:
            intent: Intent with series/episode info
            client: Sonarr client

        Returns:
            Execution result
        """
        if not intent.series_id:
            return ExecutionResult(
                success=False,
                message=f"Could not find series '{intent.title}' in library",
            )

        # If specific episodes are mentioned, delete those files
        if intent.episodes and intent.season is not None:
            # Get all episodes for the series
            all_episodes = await client.get_episodes(
                intent.series_id, season_number=intent.season
            )

            # Filter to the requested episodes
            target_episodes = [
                ep for ep in all_episodes if ep.get("episodeNumber") in intent.episodes
            ]

            if not target_episodes:
                return ExecutionResult(
                    success=False,
                    message=f"Could not find episodes {intent.episodes} in season {intent.season}",
                )

            # Get the file IDs
            file_ids = []
            for ep in target_episodes:
                if ep.get("episodeFileId"):
                    file_ids.append(ep["episodeFileId"])

            if not file_ids:
                return ExecutionResult(
                    success=False,
                    message=f"Episodes {intent.episodes} have no files to delete",
                )

            # Delete the files
            deleted_count = await client.delete_episode_files(file_ids)

            return ExecutionResult(
                success=True,
                message=f"Removed {deleted_count} episode file(s) from {intent.title} Season {intent.season}",
                data={"deleted_count": deleted_count, "file_ids": file_ids},
            )

        # If season is mentioned but no episodes, delete entire season
        elif intent.season is not None:
            all_episodes = await client.get_episodes(
                intent.series_id, season_number=intent.season
            )

            file_ids = [
                ep["episodeFileId"]
                for ep in all_episodes
                if ep.get("episodeFileId")
            ]

            if not file_ids:
                return ExecutionResult(
                    success=False,
                    message=f"Season {intent.season} has no files to delete",
                )

            deleted_count = await client.delete_episode_files(file_ids)

            return ExecutionResult(
                success=True,
                message=f"Removed {deleted_count} episode file(s) from {intent.title} Season {intent.season}",
                data={"deleted_count": deleted_count},
            )

        # Otherwise, delete entire series
        else:
            await client.delete_item(intent.series_id, delete_files=True)
            return ExecutionResult(
                success=True,
                message=f"Removed series '{intent.title}' and all files",
            )

    async def _remove_movie(
        self, intent: Intent, client: RadarrClient
    ) -> ExecutionResult:
        """Remove a movie.

        Args:
            intent: Intent with movie info
            client: Radarr client

        Returns:
            Execution result
        """
        if not intent.item_id:
            return ExecutionResult(
                success=False,
                message=f"Could not find movie '{intent.title}' in library",
            )

        await client.delete_item(intent.item_id, delete_files=True)

        return ExecutionResult(
            success=True,
            message=f"Removed movie '{intent.title}' and all files",
        )

    async def _execute_search(
        self, intent: Intent, client: BaseMediaClient
    ) -> ExecutionResult:
        """Execute a search action.

        Args:
            intent: Intent to execute
            client: Media client

        Returns:
            Execution result
        """
        # For items already in library, trigger a search
        if intent.series_id and intent.media_type.value == "tv":
            result = await client.trigger_series_search(intent.series_id)
            return ExecutionResult(
                success=True,
                message=f"Triggered search for '{intent.title}'",
                data=result,
            )
        elif intent.item_id and intent.media_type.value == "movie":
            result = await client.trigger_movie_search(intent.item_id)
            return ExecutionResult(
                success=True,
                message=f"Triggered search for '{intent.title}'",
                data=result,
            )
        else:
            # Search external sources
            results = await client.search(intent.title or "")
            return ExecutionResult(
                success=True,
                message=f"Found {len(results)} result(s) for '{intent.title}'",
                data={"results": results[:5]},  # Limit to 5 results
            )

    async def _execute_add(
        self, intent: Intent, client: BaseMediaClient
    ) -> ExecutionResult:
        """Execute an add action.

        Args:
            intent: Intent to execute
            client: Media client

        Returns:
            Execution result
        """
        # Get quality profiles and root folders
        profiles = await client.get_quality_profiles()
        root_folders = await client.get_root_folders()

        if not profiles or not root_folders:
            return ExecutionResult(
                success=False,
                message="No quality profiles or root folders configured",
            )

        # Use first available profile and root folder
        profile_id = profiles[0]["id"]
        root_folder = root_folders[0]["path"]

        if intent.media_type.value == "tv":
            # Search for the show first
            results = await client.search(intent.title)
            if not results:
                return ExecutionResult(
                    success=False,
                    message=f"Could not find '{intent.title}' to add",
                )

            # Add the first result
            show = results[0]
            added = await client.add_series(
                tvdb_id=show["tvdbId"],
                title=show["title"],
                quality_profile_id=profile_id,
                root_folder_path=root_folder,
            )

            return ExecutionResult(
                success=True,
                message=f"Added '{show['title']}' to library",
                data=added,
            )

        elif intent.media_type.value == "movie":
            # Search for the movie first
            results = await client.search(intent.title)
            if not results:
                return ExecutionResult(
                    success=False,
                    message=f"Could not find '{intent.title}' to add",
                )

            # Add the first result
            movie = results[0]
            added = await client.add_movie(
                tmdb_id=movie["tmdbId"],
                title=movie["title"],
                quality_profile_id=profile_id,
                root_folder_path=root_folder,
            )

            return ExecutionResult(
                success=True,
                message=f"Added '{movie['title']}' to library",
                data=added,
            )

        else:
            return ExecutionResult(
                success=False,
                message=f"Add not yet implemented for {intent.media_type}",
            )

    async def _execute_list(
        self, intent: Intent, client: BaseMediaClient
    ) -> ExecutionResult:
        """Execute a list action.

        Args:
            intent: Intent to execute
            client: Media client

        Returns:
            Execution result
        """
        if intent.media_type.value == "tv":
            items = await client.get_all_series()
            titles = [item["title"] for item in items]
            return ExecutionResult(
                success=True,
                message=f"Found {len(items)} TV show(s)",
                data={"titles": titles, "count": len(items)},
            )
        elif intent.media_type.value == "movie":
            items = await client.get_all_movies()
            titles = [item["title"] for item in items]
            return ExecutionResult(
                success=True,
                message=f"Found {len(items)} movie(s)",
                data={"titles": titles, "count": len(items)},
            )
        else:
            return ExecutionResult(
                success=False,
                message=f"List not yet implemented for {intent.media_type}",
            )

    async def _execute_info(
        self, intent: Intent, client: BaseMediaClient
    ) -> ExecutionResult:
        """Execute an info action.

        Args:
            intent: Intent to execute
            client: Media client

        Returns:
            Execution result
        """
        if not intent.item_id:
            return ExecutionResult(
                success=False,
                message=f"Could not find '{intent.title}' in library",
            )

        item = await client.get_item(intent.item_id)

        return ExecutionResult(
            success=True,
            message=f"Details for '{intent.title}'",
            data=item,
        )
