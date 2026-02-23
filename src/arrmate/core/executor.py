"""Intent execution orchestrator."""

import asyncio
import logging
from typing import List

from ..clients.base import BaseMediaClient
from ..clients.discovery import get_client_for_media_type
from ..clients.lidarr import LidarrClient
from ..clients.radarr import RadarrClient
from ..clients.readarr import ReadarrClient
from ..clients.sonarr import SonarrClient
from ..clients.plex import PlexClient
from ..clients.transcoder import create_job, ffmpeg_available, run_transcode_job, scan_for_transcode
from ..config.settings import settings
from .models import ActionType, ExecutionResult, Intent

logger = logging.getLogger(__name__)


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
            # These actions manage their own clients (bypass Arr routing)
            if intent.action == ActionType.TRANSCODE:
                return await self._execute_transcode(intent)
            if intent.action == ActionType.RATE:
                return await self._execute_rate(intent)
            if intent.action == ActionType.BUTLER:
                return await self._execute_butler(intent)
            if intent.action == ActionType.QUEUE:
                return await self._execute_queue(intent)
            if intent.action == ActionType.HISTORY:
                return await self._execute_history(intent)
            if intent.action == ActionType.WANTED:
                return await self._execute_wanted(intent)

            # Get the appropriate client
            client = get_client_for_media_type(intent.media_type)

            try:
                # Route to appropriate handler based on action
                if intent.action == ActionType.REMOVE or intent.action == ActionType.DELETE:
                    return await self._execute_remove(intent, client)
                elif intent.action == ActionType.SEARCH:
                    return await self._execute_search(intent, client)
                elif intent.action == ActionType.UPGRADE:
                    return await self._execute_upgrade(intent, client)
                elif intent.action == ActionType.ADD:
                    return await self._execute_add(intent, client)
                elif intent.action == ActionType.LIST:
                    return await self._execute_list(intent, client)
                elif intent.action == ActionType.INFO:
                    return await self._execute_info(intent, client)
                elif intent.action == ActionType.MONITOR:
                    return await self._execute_monitor(intent, client, monitored=True)
                elif intent.action == ActionType.UNMONITOR:
                    return await self._execute_monitor(intent, client, monitored=False)
                elif intent.action == ActionType.RENAME:
                    return await self._execute_rename(intent, client)
                elif intent.action == ActionType.RESCAN:
                    return await self._execute_rescan(intent, client)
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
        if intent.media_type == "tv":
            return await self._remove_tv_content(intent, client)
        elif intent.media_type == "movie":
            return await self._remove_movie(intent, client)
        elif intent.media_type == "music":
            return await self._remove_music_content(intent, client)
        elif intent.media_type in ("audiobook", "book"):
            return await self._remove_book_content(intent, client)
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

    async def _remove_music_content(
        self, intent: Intent, client: LidarrClient
    ) -> ExecutionResult:
        """Remove music (artist).

        Args:
            intent: Intent with artist info
            client: Lidarr client

        Returns:
            Execution result
        """
        if not intent.item_id:
            return ExecutionResult(
                success=False,
                message=f"Could not find artist '{intent.title}' in library",
            )

        await client.delete_item(intent.item_id, delete_files=True)

        return ExecutionResult(
            success=True,
            message=f"Removed artist '{intent.title}' and all files",
        )

    async def _remove_book_content(
        self, intent: Intent, client: ReadarrClient
    ) -> ExecutionResult:
        """Remove book/audiobook (author).

        Args:
            intent: Intent with author info
            client: Readarr client

        Returns:
            Execution result
        """
        logger.warning("Using deprecated Readarr client for removal")

        if not intent.item_id:
            return ExecutionResult(
                success=False,
                message=f"Could not find author '{intent.title}' in library",
            )

        await client.delete_item(intent.item_id, delete_files=True)

        return ExecutionResult(
            success=True,
            message=f"Removed author '{intent.title}' and all files",
        )

    async def _execute_upgrade(
        self, intent: Intent, client: BaseMediaClient
    ) -> ExecutionResult:
        """Execute an upgrade action — search Sonarr/Radarr for a better version.

        Routes to episode-, season-, or series-level search depending on specificity.
        """
        if intent.media_type == "tv" and intent.series_id:
            if intent.episodes and intent.season is not None:
                # Specific episode(s): fetch Sonarr episode IDs and run EpisodeSearch
                all_episodes = await client.get_episodes(
                    intent.series_id, season_number=intent.season
                )
                episode_ids = [
                    ep["id"]
                    for ep in all_episodes
                    if ep.get("episodeNumber") in intent.episodes
                ]
                if not episode_ids:
                    ep_str = ", ".join(str(e) for e in intent.episodes)
                    return ExecutionResult(
                        success=False,
                        message=(
                            f"Could not find episode(s) {ep_str} in "
                            f"Season {intent.season} of '{intent.title}'"
                        ),
                    )
                result = await client.trigger_episode_search(episode_ids)
                ep_str = ", ".join(str(e) for e in intent.episodes)
                return ExecutionResult(
                    success=True,
                    message=f"Triggered search for '{intent.title}' S{intent.season:02d}E{ep_str}",
                    data=result,
                )
            elif intent.season is not None:
                # Whole season
                result = await client.trigger_season_search(intent.series_id, intent.season)
                return ExecutionResult(
                    success=True,
                    message=f"Triggered search for '{intent.title}' Season {intent.season}",
                    data=result,
                )
            else:
                # Whole series
                result = await client.trigger_series_search(intent.series_id)
                return ExecutionResult(
                    success=True,
                    message=f"Triggered search for '{intent.title}'",
                    data=result,
                )
        elif intent.media_type == "movie" and intent.item_id:
            result = await client.trigger_movie_search(intent.item_id)
            return ExecutionResult(
                success=True,
                message=f"Triggered search for '{intent.title}'",
                data=result,
            )
        else:
            return ExecutionResult(
                success=False,
                message=f"Could not find '{intent.title}' in library to upgrade",
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
        if intent.series_id and intent.media_type == "tv":
            result = await client.trigger_series_search(intent.series_id)
            return ExecutionResult(
                success=True,
                message=f"Triggered search for '{intent.title}'",
                data=result,
            )
        elif intent.item_id and intent.media_type == "movie":
            result = await client.trigger_movie_search(intent.item_id)
            return ExecutionResult(
                success=True,
                message=f"Triggered search for '{intent.title}'",
                data=result,
            )
        elif intent.item_id and intent.media_type == "music":
            result = await client.trigger_artist_search(intent.item_id)
            return ExecutionResult(
                success=True,
                message=f"Triggered search for '{intent.title}'",
                data=result,
            )
        elif intent.item_id and intent.media_type in ("audiobook", "book"):
            result = await client.trigger_author_search(intent.item_id)
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
        # If the item is already in the library, route to upgrade/search instead
        if intent.series_id and intent.media_type == "tv":
            return await self._execute_upgrade(intent, client)
        if intent.item_id and intent.media_type == "movie":
            return await self._execute_upgrade(intent, client)

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

        if intent.media_type == "tv":
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

        elif intent.media_type == "movie":
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
        if intent.media_type == "tv":
            items = await client.get_all_series()
            titles = [item["title"] for item in items]
            return ExecutionResult(
                success=True,
                message=f"Found {len(items)} TV show(s)",
                data={"titles": titles, "count": len(items)},
            )
        elif intent.media_type == "movie":
            items = await client.get_all_movies()
            titles = [item["title"] for item in items]
            return ExecutionResult(
                success=True,
                message=f"Found {len(items)} movie(s)",
                data={"titles": titles, "count": len(items)},
            )
        elif intent.media_type == "music":
            items = await client.get_all_artists()
            titles = [item.get("artistName", item.get("title", "Unknown")) for item in items]
            return ExecutionResult(
                success=True,
                message=f"Found {len(items)} artist(s)",
                data={"titles": titles, "count": len(items)},
            )
        elif intent.media_type in ("audiobook", "book"):
            logger.warning("Using deprecated Readarr client for listing")
            items = await client.get_all_authors()
            titles = [item.get("authorName", item.get("title", "Unknown")) for item in items]
            return ExecutionResult(
                success=True,
                message=f"Found {len(items)} author(s)",
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

    async def _execute_transcode(self, intent: Intent) -> ExecutionResult:
        """Scan library for non-H265 files and start a background transcode job.

        Args:
            intent: Intent with media_type and optional title filter

        Returns:
            Execution result with job ID and file count
        """
        if not ffmpeg_available():
            return ExecutionResult(
                success=False,
                message="ffmpeg is not installed. Add ffmpeg to your Dockerfile or install it on the host.",
            )

        media_type = intent.media_type or "movie"
        title = intent.title

        try:
            files = await scan_for_transcode(media_type=media_type, title=title)
        except Exception as exc:
            return ExecutionResult(
                success=False,
                message=f"Failed to scan library: {exc}",
                errors=[str(exc)],
            )

        if not files:
            scope = f"'{title}'" if title else f"all {media_type} files"
            return ExecutionResult(
                success=True,
                message=f"No files need transcoding for {scope} — everything is already H.265!",
            )

        job_id = create_job(files, media_type=media_type, title=title)
        asyncio.create_task(run_transcode_job(job_id, files))

        scope = f"'{title}'" if title else f"your {media_type} library"
        total_size = sum(f.get("size", 0) for f in files)
        size_str = _fmt_bytes(total_size)

        return ExecutionResult(
            success=True,
            message=(
                f"Started H.265 transcode job for {scope}: "
                f"{len(files)} file(s) queued (~{size_str} total). "
                f"Job ID: {job_id}. Track progress at /web/transcode"
            ),
            data={
                "job_id": job_id,
                "files_queued": len(files),
                "total_size": size_str,
                "media_type": media_type,
                "title_filter": title,
            },
        )


    async def _execute_rate(self, intent: Intent) -> ExecutionResult:
        """Rate a Plex item using natural language (e.g. 'rate The Matrix 5 stars').

        Searches Plex for the title and applies the star rating.
        """
        if not settings.plex_url or not settings.plex_token:
            return ExecutionResult(success=False, message="Plex is not configured")

        if not intent.title:
            return ExecutionResult(success=False, message="No title specified for rating")

        stars = float((intent.criteria or {}).get("rating", 5))
        client = PlexClient(settings.plex_url, settings.plex_token)
        try:
            hubs = await client.search(intent.title, limit=5)
            rating_key = None
            for hub in hubs:
                for item in hub.get("Metadata", []):
                    if intent.title.lower() in item.get("title", "").lower():
                        rating_key = item.get("ratingKey")
                        break
                if rating_key:
                    break

            if not rating_key:
                return ExecutionResult(
                    success=False,
                    message=f"Could not find '{intent.title}' in Plex",
                )

            ok = await client.rate_item(rating_key, stars)
            if ok:
                return ExecutionResult(
                    success=True,
                    message=f"Rated '{intent.title}' {int(stars)} star(s) in Plex",
                )
            return ExecutionResult(
                success=False, message=f"Failed to rate '{intent.title}' in Plex"
            )
        finally:
            await client.close()

    async def _execute_butler(self, intent: Intent) -> ExecutionResult:
        """Run a Plex Butler maintenance task (e.g. 'clean plex database')."""
        if not settings.plex_url or not settings.plex_token:
            return ExecutionResult(success=False, message="Plex is not configured")

        task = (intent.criteria or {}).get("task", "CleanOldBundles")
        client = PlexClient(settings.plex_url, settings.plex_token)
        try:
            ok = await client.run_butler_task(task)
            if ok:
                return ExecutionResult(
                    success=True,
                    message=f"Started Plex maintenance task: {task}",
                    data={"task": task},
                )
            return ExecutionResult(
                success=False, message=f"Failed to start Plex task: {task}"
            )
        finally:
            await client.close()


    async def _execute_queue(self, intent: Intent) -> ExecutionResult:
        """Show what is currently downloading in Sonarr and/or Radarr."""
        import time as _time
        items: List[dict] = []
        sources: List[str] = []

        if intent.media_type in ("tv", "tv_show") or intent.media_type == "tv":
            if settings.sonarr_url and settings.sonarr_api_key:
                try:
                    from ..clients.sonarr import SonarrClient
                    c = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
                    resp = await c.get_queue()
                    await c.close()
                    for r in (resp.get("records") or []):
                        series = r.get("series") or {}
                        ep = r.get("episode") or {}
                        size = r.get("size", 0)
                        size_left = r.get("sizeleft", 0)
                        pct = int((size - size_left) / size * 100) if size else 0
                        eta = r.get("estimatedCompletionTime", "")
                        items.append({
                            "kind": "tv",
                            "show": series.get("title", ""),
                            "episode": f"S{ep.get('seasonNumber',0):02d}E{ep.get('episodeNumber',0):02d}" if ep else "",
                            "title": r.get("title", ""),
                            "status": r.get("status", ""),
                            "progress": pct,
                            "eta": eta[:16] if eta else "",
                            "protocol": r.get("protocol", ""),
                            "quality": (r.get("quality") or {}).get("quality", {}).get("name", ""),
                        })
                    sources.append("Sonarr")
                except Exception:
                    pass

        if intent.media_type == "movie" or intent.media_type == "tv":
            if settings.radarr_url and settings.radarr_api_key:
                try:
                    from ..clients.radarr import RadarrClient
                    c = RadarrClient(settings.radarr_url, settings.radarr_api_key)
                    resp = await c.get_queue()
                    await c.close()
                    for r in (resp.get("records") or []):
                        movie = r.get("movie") or {}
                        size = r.get("size", 0)
                        size_left = r.get("sizeleft", 0)
                        pct = int((size - size_left) / size * 100) if size else 0
                        eta = r.get("estimatedCompletionTime", "")
                        items.append({
                            "kind": "movie",
                            "show": "",
                            "episode": "",
                            "title": movie.get("title") or r.get("title", ""),
                            "status": r.get("status", ""),
                            "progress": pct,
                            "eta": eta[:16] if eta else "",
                            "protocol": r.get("protocol", ""),
                            "quality": (r.get("quality") or {}).get("quality", {}).get("name", ""),
                        })
                    if "Radarr" not in sources:
                        sources.append("Radarr")
                except Exception:
                    pass

        if not items:
            return ExecutionResult(
                success=True,
                message="The download queue is empty.",
                data={"data_type": "queue", "items": [], "total": 0},
            )
        src_str = " + ".join(sources) if sources else "queue"
        return ExecutionResult(
            success=True,
            message=f"{len(items)} item(s) currently downloading ({src_str})",
            data={"data_type": "queue", "items": items, "total": len(items)},
        )

    async def _execute_history(self, intent: Intent) -> ExecutionResult:
        """Show recent download/import history from Sonarr and/or Radarr."""
        EVENT_LABELS = {
            "grabbed": "Grabbed",
            "downloadFolderImported": "Imported",
            "downloadFailed": "Failed",
            "episodeFileDeleted": "Deleted",
            "episodeFileRenamed": "Renamed",
            "downloadIgnored": "Ignored",
        }
        items: List[dict] = []

        if intent.media_type != "movie":
            if settings.sonarr_url and settings.sonarr_api_key:
                try:
                    from ..clients.sonarr import SonarrClient
                    c = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
                    resp = await c.get_history(page_size=20)
                    await c.close()
                    for r in (resp.get("records") or []):
                        series = r.get("series") or {}
                        ep = r.get("episode") or {}
                        items.append({
                            "kind": "tv",
                            "show": series.get("title", ""),
                            "episode": f"S{ep.get('seasonNumber',0):02d}E{ep.get('episodeNumber',0):02d}" if ep else "",
                            "title": r.get("sourceTitle", ""),
                            "event": EVENT_LABELS.get(r.get("eventType", ""), r.get("eventType", "")),
                            "date": (r.get("date") or "")[:10],
                            "quality": (r.get("quality") or {}).get("quality", {}).get("name", ""),
                        })
                except Exception:
                    pass

        if intent.media_type != "tv":
            if settings.radarr_url and settings.radarr_api_key:
                try:
                    from ..clients.radarr import RadarrClient
                    c = RadarrClient(settings.radarr_url, settings.radarr_api_key)
                    resp = await c.get_history(page_size=20)
                    await c.close()
                    for r in (resp.get("records") or []):
                        movie = r.get("movie") or {}
                        items.append({
                            "kind": "movie",
                            "show": "",
                            "episode": "",
                            "title": movie.get("title") or r.get("sourceTitle", ""),
                            "event": EVENT_LABELS.get(r.get("eventType", ""), r.get("eventType", "")),
                            "date": (r.get("date") or "")[:10],
                            "quality": (r.get("quality") or {}).get("quality", {}).get("name", ""),
                        })
                except Exception:
                    pass

        # Sort combined results by date descending
        items.sort(key=lambda x: x.get("date", ""), reverse=True)
        items = items[:30]

        if not items:
            return ExecutionResult(success=True, message="No recent download history found.")
        return ExecutionResult(
            success=True,
            message=f"{len(items)} recent download event(s)",
            data={"data_type": "history", "items": items, "total": len(items)},
        )

    async def _execute_wanted(self, intent: Intent) -> ExecutionResult:
        """Show monitored media that is missing or below quality cutoff."""
        items: List[dict] = []

        if intent.media_type != "movie":
            if settings.sonarr_url and settings.sonarr_api_key:
                try:
                    from ..clients.sonarr import SonarrClient
                    c = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
                    resp = await c.get_wanted_missing(page_size=30)
                    await c.close()
                    for r in (resp.get("records") or []):
                        series = r.get("series") or {}
                        items.append({
                            "kind": "tv",
                            "show": series.get("title", ""),
                            "episode": f"S{r.get('seasonNumber',0):02d}E{r.get('episodeNumber',0):02d}",
                            "title": r.get("title", ""),
                            "air_date": (r.get("airDate") or "")[:10],
                        })
                except Exception:
                    pass

        if intent.media_type != "tv":
            if settings.radarr_url and settings.radarr_api_key:
                try:
                    from ..clients.radarr import RadarrClient
                    c = RadarrClient(settings.radarr_url, settings.radarr_api_key)
                    resp = await c.get_wanted_cutoff(page_size=30)
                    await c.close()
                    for r in (resp.get("records") or []):
                        items.append({
                            "kind": "movie",
                            "show": "",
                            "episode": "",
                            "title": r.get("title", ""),
                            "air_date": (r.get("inCinemas") or r.get("physicalRelease") or "")[:10],
                        })
                except Exception:
                    pass

        if not items:
            return ExecutionResult(success=True, message="Nothing is missing — great!")
        return ExecutionResult(
            success=True,
            message=f"{len(items)} item(s) missing or below quality cutoff",
            data={"data_type": "wanted", "items": items, "total": len(items)},
        )

    async def _execute_monitor(
        self, intent: Intent, client: BaseMediaClient, monitored: bool
    ) -> ExecutionResult:
        """Monitor or unmonitor a series/movie/season."""
        verb = "Monitoring" if monitored else "Unmonitoring"
        if intent.media_type == "tv":
            if not intent.series_id:
                return ExecutionResult(
                    success=False, message=f"Could not find '{intent.title}' in Sonarr"
                )
            if intent.season is not None:
                # Monitor/unmonitor specific season
                series = await client.get_item(intent.series_id)
                for s in series.get("seasons", []):
                    if s.get("seasonNumber") == intent.season:
                        s["monitored"] = monitored
                from ..clients.sonarr import SonarrClient
                await client._put(f"api/v3/series/{intent.series_id}", data=series)
                return ExecutionResult(
                    success=True,
                    message=f"{verb} '{intent.title}' Season {intent.season}",
                )
            else:
                await client.set_series_monitored(intent.series_id, monitored)
                return ExecutionResult(
                    success=True, message=f"{verb} '{intent.title}'"
                )
        elif intent.media_type == "movie":
            if not intent.item_id:
                return ExecutionResult(
                    success=False, message=f"Could not find '{intent.title}' in Radarr"
                )
            await client.set_movie_monitored(intent.item_id, monitored)
            return ExecutionResult(
                success=True, message=f"{verb} '{intent.title}'"
            )
        return ExecutionResult(
            success=False, message=f"Monitor not supported for {intent.media_type}"
        )

    async def _execute_rename(
        self, intent: Intent, client: BaseMediaClient
    ) -> ExecutionResult:
        """Trigger file rename for a series or movie."""
        if intent.media_type == "tv":
            if not intent.series_id:
                return ExecutionResult(
                    success=False, message=f"Could not find '{intent.title}' in Sonarr"
                )
            from ..clients.sonarr import SonarrClient
            result = await client.trigger_rename_series(intent.series_id)
            return ExecutionResult(
                success=True,
                message=f"Rename triggered for '{intent.title}' — files will be renamed to match your naming convention",
            )
        elif intent.media_type == "movie":
            if not intent.item_id:
                return ExecutionResult(
                    success=False, message=f"Could not find '{intent.title}' in Radarr"
                )
            from ..clients.radarr import RadarrClient
            result = await client.trigger_rename_movie(intent.item_id)
            return ExecutionResult(
                success=True,
                message=f"Rename triggered for '{intent.title}'",
            )
        return ExecutionResult(
            success=False, message=f"Rename not supported for {intent.media_type}"
        )

    async def _execute_rescan(
        self, intent: Intent, client: BaseMediaClient
    ) -> ExecutionResult:
        """Trigger disk rescan for a series or movie."""
        if intent.media_type == "tv":
            if not intent.series_id:
                return ExecutionResult(
                    success=False, message=f"Could not find '{intent.title}' in Sonarr"
                )
            from ..clients.sonarr import SonarrClient
            await client.rescan_series(intent.series_id)
            return ExecutionResult(
                success=True,
                message=f"Disk rescan started for '{intent.title}'",
            )
        elif intent.media_type == "movie":
            if not intent.item_id:
                return ExecutionResult(
                    success=False, message=f"Could not find '{intent.title}' in Radarr"
                )
            from ..clients.radarr import RadarrClient
            await client.rescan_movie(intent.item_id)
            return ExecutionResult(
                success=True,
                message=f"Disk rescan started for '{intent.title}'",
            )
        return ExecutionResult(
            success=False, message=f"Rescan not supported for {intent.media_type}"
        )


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"
