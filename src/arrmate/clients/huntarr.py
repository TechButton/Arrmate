"""huntarr.io API client implementation.

huntarr.io is an orchestration and automation layer that works across
multiple *arr services (Sonarr, Radarr, Lidarr, etc.) to coordinate
hunts, manage backups, and provide centralized monitoring.
"""

from typing import Any, Dict, List, Optional

from .base_external import BaseExternalService


class HuntarrClient(BaseExternalService):
    """Client for huntarr.io API.

    huntarr.io is an external orchestration service that coordinates
    actions across multiple *arr services, manages backups, and provides
    centralized statistics.
    """

    async def test_connection(self) -> bool:
        """Test connection to huntarr.io.

        Returns:
            True if connection successful
        """
        try:
            await self.get_stats()
            return True
        except Exception:
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics across all connected apps.

        Returns:
            Dictionary containing statistics for all connected services
        """
        return await self._get("api/stats")

    async def get_settings(self) -> Dict[str, Any]:
        """Get general settings.

        Returns:
            Current general settings
        """
        return await self._get("api/settings/general")

    async def update_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update general settings.

        Args:
            settings: Settings to update

        Returns:
            Updated settings
        """
        return await self._post("api/settings/general", data=settings)

    async def get_instances(self, app_type: str) -> List[Dict[str, Any]]:
        """Get instances of a specific app type.

        Args:
            app_type: Type of app (sonarr, radarr, lidarr, readarr, whisparr, prowlarr, swaparr)

        Returns:
            List of configured instances
        """
        result = await self._get(f"api/instances/{app_type}")
        return result.get("data", [])

    async def create_instance(
        self, app_type: str, instance_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new app instance.

        Args:
            app_type: Type of app
            instance_data: Instance configuration (name, url, api_key, etc.)

        Returns:
            Created instance details
        """
        return await self._post(f"api/instances/{app_type}", data=instance_data)

    async def delete_instance(self, app_type: str, instance_id: str) -> bool:
        """Delete an app instance.

        Args:
            app_type: Type of app
            instance_id: Instance ID to delete

        Returns:
            True if successful
        """
        await self._delete(f"api/instances/{app_type}/{instance_id}")
        return True

    async def get_logs(
        self,
        app_type: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieve logs with optional filtering.

        Args:
            app_type: Filter by app type (sonarr, radarr, etc.)
            level: Filter by log level (ERROR, WARN, INFO, DEBUG)
            limit: Maximum number of log entries

        Returns:
            List of log entries
        """
        params = {"limit": limit}
        if app_type:
            params["app_type"] = app_type
        if level:
            params["level"] = level

        result = await self._get("api/logs", params=params)
        return result.get("data", [])

    async def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups.

        Returns:
            List of backup metadata
        """
        result = await self._get("api/backup/list")
        return result.get("data", [])

    async def create_backup(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new backup.

        Args:
            name: Optional backup name

        Returns:
            Backup creation result
        """
        data = {}
        if name:
            data["name"] = name
        return await self._post("api/backup/create", data=data)

    async def restore_backup(self, backup_id: str) -> Dict[str, Any]:
        """Restore from a backup.

        Args:
            backup_id: ID of backup to restore

        Returns:
            Restore operation result
        """
        return await self._post(f"api/backup/restore/{backup_id}")

    async def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup.

        Args:
            backup_id: ID of backup to delete

        Returns:
            True if successful
        """
        await self._delete(f"api/backup/delete/{backup_id}")
        return True

    async def get_schedules(self) -> List[Dict[str, Any]]:
        """Get all scheduled tasks.

        Returns:
            List of scheduled tasks
        """
        result = await self._get("api/schedules")
        return result.get("data", [])

    async def create_schedule(self, schedule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new scheduled task.

        Args:
            schedule_data: Schedule configuration

        Returns:
            Created schedule
        """
        return await self._post("api/schedules", data=schedule_data)

    async def update_schedule(
        self, schedule_id: str, schedule_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a scheduled task.

        Args:
            schedule_id: Schedule ID
            schedule_data: Updated schedule configuration

        Returns:
            Updated schedule
        """
        return await self._put(f"api/schedules/{schedule_id}", data=schedule_data)

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a scheduled task.

        Args:
            schedule_id: Schedule ID to delete

        Returns:
            True if successful
        """
        await self._delete(f"api/schedules/{schedule_id}")
        return True

    async def get_movie_hunt_movies(self) -> List[Dict[str, Any]]:
        """Get movies in hunt library.

        Returns:
            List of movies being tracked
        """
        result = await self._get("api/movie-hunt/movies")
        return result.get("data", [])

    async def get_movie_hunt_history(self, tmdb_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get movie hunt history.

        Args:
            tmdb_id: Optional TMDB ID to filter by

        Returns:
            List of hunt history entries
        """
        params = {}
        if tmdb_id:
            params["tmdb_id"] = tmdb_id

        result = await self._get("api/movie-hunt/history", params=params)
        return result.get("data", [])

    async def get_notification_connections(self) -> List[Dict[str, Any]]:
        """Get configured notification connections.

        Returns:
            List of notification services
        """
        result = await self._get("api/notifications/connections")
        return result.get("data", [])

    async def test_notification(self, connection_id: str) -> Dict[str, Any]:
        """Send a test notification.

        Args:
            connection_id: Notification connection ID

        Returns:
            Test result
        """
        return await self._post(f"api/notifications/connections/{connection_id}/test")
