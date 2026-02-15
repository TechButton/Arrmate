"""Lidarr API client implementation."""

from typing import Any, Dict, List, Optional

from .base import BaseMediaClient


class LidarrClient(BaseMediaClient):
    """Client for Lidarr v3 API (Music)."""

    async def test_connection(self) -> bool:
        """Test connection to Lidarr.

        Returns:
            True if connection successful
        """
        try:
            await self.get_system_status()
            return True
        except Exception:
            return False

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search for artists.

        Args:
            query: Artist name to search for

        Returns:
            List of matching artists from lookup
        """
        return await self._get("api/v3/artist/lookup", params={"term": query})

    async def get_item(self, item_id: int) -> Dict[str, Any]:
        """Get artist details by ID.

        Args:
            item_id: Artist ID

        Returns:
            Artist details
        """
        return await self._get(f"api/v3/artist/{item_id}")

    async def delete_item(self, item_id: int, delete_files: bool = False) -> bool:
        """Delete an artist.

        Args:
            item_id: Artist ID
            delete_files: Whether to delete all files

        Returns:
            True if successful
        """
        params = {"deleteFiles": str(delete_files).lower()}
        await self._delete(
            f"api/v3/artist/{item_id}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
        )
        return True

    async def get_all_artists(self) -> List[Dict[str, Any]]:
        """Get all artists in the library.

        Returns:
            List of all artists
        """
        return await self._get("api/v3/artist")

    async def add_artist(
        self,
        foreign_artist_id: str,
        artist_name: str,
        quality_profile_id: int,
        metadata_profile_id: int,
        root_folder_path: str,
        monitored: bool = True,
        search_for_missing: bool = True,
    ) -> Dict[str, Any]:
        """Add a new artist to the library.

        Args:
            foreign_artist_id: MusicBrainz Artist ID
            artist_name: Artist name
            quality_profile_id: Quality profile ID
            metadata_profile_id: Metadata profile ID
            root_folder_path: Root folder path
            monitored: Whether to monitor the artist
            search_for_missing: Whether to search for missing albums

        Returns:
            Added artist details
        """
        data = {
            "foreignArtistId": foreign_artist_id,
            "artistName": artist_name,
            "qualityProfileId": quality_profile_id,
            "metadataProfileId": metadata_profile_id,
            "rootFolderPath": root_folder_path,
            "monitored": monitored,
            "addOptions": {"searchForMissingAlbums": search_for_missing},
        }
        return await self._post("api/v3/artist", data=data)

    async def get_albums(self, artist_id: int) -> List[Dict[str, Any]]:
        """Get albums for an artist.

        Args:
            artist_id: Artist ID

        Returns:
            List of albums
        """
        return await self._get("api/v3/album", params={"artistId": artist_id})

    async def get_tracks(self, album_id: int) -> List[Dict[str, Any]]:
        """Get tracks for an album.

        Args:
            album_id: Album ID

        Returns:
            List of tracks
        """
        return await self._get("api/v3/track", params={"albumId": album_id})

    async def get_track_files(self, artist_id: int) -> List[Dict[str, Any]]:
        """Get track files for an artist.

        Args:
            artist_id: Artist ID

        Returns:
            List of track files
        """
        return await self._get("api/v3/trackfile", params={"artistId": artist_id})

    async def delete_track_file(self, file_id: int) -> bool:
        """Delete a track file.

        Args:
            file_id: Track file ID

        Returns:
            True if successful
        """
        await self._delete(f"api/v3/trackfile/{file_id}")
        return True

    async def trigger_artist_search(self, artist_id: int) -> Dict[str, Any]:
        """Trigger a search for all missing albums of an artist.

        Args:
            artist_id: Artist ID

        Returns:
            Command response
        """
        return await self._post(
            "api/v3/command",
            data={"name": "ArtistSearch", "artistId": artist_id},
        )

    async def trigger_album_search(self, album_ids: List[int]) -> Dict[str, Any]:
        """Trigger a search for specific albums.

        Args:
            album_ids: List of album IDs

        Returns:
            Command response
        """
        return await self._post(
            "api/v3/command",
            data={"name": "AlbumSearch", "albumIds": album_ids},
        )

    async def get_quality_profiles(self) -> List[Dict[str, Any]]:
        """Get available quality profiles.

        Returns:
            List of quality profiles
        """
        return await self._get("api/v3/qualityprofile")

    async def get_metadata_profiles(self) -> List[Dict[str, Any]]:
        """Get available metadata profiles.

        Returns:
            List of metadata profiles
        """
        return await self._get("api/v3/metadataprofile")

    async def get_root_folders(self) -> List[Dict[str, Any]]:
        """Get available root folders.

        Returns:
            List of root folders
        """
        return await self._get("api/v3/rootfolder")
