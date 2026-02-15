"""Tool/function calling schemas for LLM providers."""

from typing import Any, Dict, List, Optional

# Tool schema for parsing media commands
PARSE_MEDIA_COMMAND_SCHEMA = {
    "name": "parse_media_command",
    "description": "Extract structured intent from a natural language media management command",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "remove",
                    "search",
                    "add",
                    "upgrade",
                    "list",
                    "info",
                    "delete",
                    "download_subtitle",
                    "sync_subtitles",
                ],
                "description": (
                    "The action to perform: "
                    "'remove'/'delete' = delete files from library, "
                    "'search' = search for media or trigger a library search, "
                    "'add' = add to library, "
                    "'upgrade' = upgrade media quality, "
                    "'list' = list items (library contents, Plex sessions, libraries, etc.), "
                    "'info' = get details about a specific item, "
                    "'download_subtitle' = download missing subtitles via Bazarr, "
                    "'sync_subtitles' = sync existing subtitles via Bazarr"
                ),
            },
            "media_type": {
                "type": "string",
                "enum": ["tv", "movie", "music", "audiobook", "book", "adult"],
                "description": (
                    "Type of media: 'tv'=TV shows/series, 'movie'=films, "
                    "'music'=songs/artists/albums, 'audiobook'=audio books, "
                    "'book'=ebooks/written books, 'adult'=adult content. "
                    "For Plex or cross-service commands with no clear type, default to 'tv'."
                ),
            },
            "title": {
                "type": "string",
                "description": (
                    "The title of the show, movie, album, audiobook, or artist. "
                    "Extract the exact name as mentioned. Omit if not specified."
                ),
            },
            "season": {
                "type": "integer",
                "description": "Season number for TV shows only (e.g., 'season 1' = 1).",
            },
            "episodes": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "Episode numbers for TV shows. Extract all mentioned "
                    "(e.g., 'episodes 1 and 2' = [1, 2], 'episode 5' = [5])."
                ),
            },
            "criteria": {
                "type": "object",
                "description": "Additional filter, search, or service-routing criteria",
                "properties": {
                    "language": {
                        "type": "string",
                        "description": (
                            "Language code or name (e.g., 'en', 'English', 'all English')"
                        ),
                    },
                    "quality": {
                        "type": "string",
                        "description": "Quality preference (e.g., '4K', '1080p', 'BluRay')",
                    },
                    "year": {
                        "type": "integer",
                        "description": "Release year for disambiguation",
                    },
                    "service": {
                        "type": "string",
                        "description": (
                            "Target a specific service when the command is explicitly about it. "
                            "Use 'plex' for Plex Media Server operations, 'bazarr' for subtitle "
                            "management, 'audiobookshelf' for AudioBookshelf, 'huntarr' for "
                            "huntarr.io orchestration. Leave unset for standard *arr operations."
                        ),
                    },
                    "operation": {
                        "type": "string",
                        "description": (
                            "Service-specific operation name. "
                            "Plex operations: 'refresh' (refresh metadata for an item), "
                            "'scan' (scan/re-index a library), 'sessions' (show active streams), "
                            "'watched' (mark item as watched), 'unwatched' (mark as unwatched), "
                            "'trash' (empty library trash). "
                            "Bazarr operations: 'missing' (list items with missing subtitles)."
                        ),
                    },
                },
                "additionalProperties": True,
            },
        },
        "required": ["action", "media_type"],
    },
}


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Get all available tool schemas for LLM function calling."""
    return [PARSE_MEDIA_COMMAND_SCHEMA]


def get_system_prompt(available_services: Optional[List[str]] = None) -> str:
    """Get the system prompt for command parsing.

    Args:
        available_services: List of service names that are configured and reachable.
            When provided, the prompt includes service context and warns about
            unavailable media types.

    Returns:
        System prompt string
    """
    service_context = _build_service_context(available_services)

    return f"""You are a media management assistant that extracts structured intent from natural language commands.
{service_context}
Your job is to parse commands about managing TV shows, movies, music, audiobooks, books, and other media across multiple services.

Key guidelines:
- Extract the ACTION (remove/delete, search, add, upgrade, list, info, download_subtitle, sync_subtitles)
- Identify the MEDIA TYPE (tv, movie, music, audiobook, book, adult)
- Extract the TITLE exactly as mentioned
- For TV shows, extract SEASON and EPISODE numbers if mentioned
- Extract any CRITERIA (language, quality, year, service, operation)
- Set criteria.service when the command targets a specific service (plex, bazarr, etc.)
- Set criteria.operation for service-specific operations (refresh, scan, sessions, watched, etc.)

Standard *arr examples:
- "remove episode 1 and 2 of Angel season 1" → action=remove, media_type=tv, title="Angel", season=1, episodes=[1,2]
- "add Breaking Bad to my library" → action=add, media_type=tv, title="Breaking Bad"
- "find 4K version of Blade Runner" → action=search, media_type=movie, title="Blade Runner", criteria={{quality: "4K"}}
- "show me all my TV shows" → action=list, media_type=tv
- "search for an all English version" → action=search, media_type=tv, criteria={{language: "English"}}
- "delete The Office and all its files" → action=delete, media_type=tv, title="The Office"
- "redownload Ghosts season 1 episode 1" → action=search, media_type=tv, title="Ghosts", season=1, episodes=[1]
- "re-download a new version of The Wire S02E05" → action=search, media_type=tv, title="The Wire", season=2, episodes=[5]
- "get a better copy of Inception" → action=search, media_type=movie, title="Inception"
- "upgrade The Matrix to 4K" → action=upgrade, media_type=movie, title="The Matrix", criteria={{quality: "4K"}}
- "check for new versions of Firefly" → action=search, media_type=tv, title="Firefly"

Plex examples:
- "what's playing on Plex" → action=list, media_type=tv, criteria={{service: "plex", operation: "sessions"}}
- "show active Plex streams" → action=list, media_type=tv, criteria={{service: "plex", operation: "sessions"}}
- "refresh Plex metadata for Breaking Bad" → action=search, media_type=tv, title="Breaking Bad", criteria={{service: "plex", operation: "refresh"}}
- "scan my Plex libraries" → action=list, media_type=tv, criteria={{service: "plex", operation: "scan"}}
- "mark The Sopranos as watched in Plex" → action=info, media_type=tv, title="The Sopranos", criteria={{service: "plex", operation: "watched"}}
- "show my Plex libraries" → action=list, media_type=tv, criteria={{service: "plex"}}
- "empty Plex trash" → action=delete, media_type=tv, criteria={{service: "plex", operation: "trash"}}

Subtitle examples (Bazarr):
- "download missing subtitles for The Wire" → action=download_subtitle, media_type=tv, title="The Wire"
- "get English subtitles for Inception" → action=download_subtitle, media_type=movie, title="Inception", criteria={{language: "English"}}
- "sync subtitles for Breaking Bad season 3" → action=sync_subtitles, media_type=tv, title="Breaking Bad", season=3
- "what shows are missing subtitles" → action=list, media_type=tv, criteria={{service: "bazarr", operation: "missing"}}

Audiobook / book examples:
- "list my audiobooks" → action=list, media_type=audiobook
- "search for Dune audiobook" → action=search, media_type=audiobook, title="Dune"
- "add Terry Pratchett books" → action=add, media_type=book, title="Terry Pratchett"
- "show my audiobook library" → action=list, media_type=audiobook, criteria={{service: "audiobookshelf"}}

Always use the parse_media_command function to return structured data."""


def _build_service_context(available_services: Optional[List[str]]) -> str:
    """Build the service-awareness section of the system prompt.

    Args:
        available_services: List of available service names, or None if unknown.

    Returns:
        Formatted context string (may be empty)
    """
    if not available_services:
        return ""

    service_descriptions = {
        "sonarr": "TV show management — search, add, remove, list",
        "radarr": "Movie management — search, add, remove, list",
        "lidarr": "Music management — artists, albums, tracks",
        "whisparr": "Adult content management",
        "bazarr": "Subtitle download and sync for TV shows and movies",
        "audiobookshelf": "Audiobook and podcast player — browse, search, progress",
        "lazylibrarian": "Book and audiobook management with automated downloading",
        "huntarr": "Orchestration and statistics across *arr services",
        "plex": (
            "Media server — browse libraries, cross-library search, active sessions, "
            "refresh metadata, scan libraries, mark watched/unwatched"
        ),
        "readarr": "Book/audiobook management (DEPRECATED — project retired)",
    }

    lines = ["\nCurrently available services:"]
    for svc in available_services:
        desc = service_descriptions.get(svc, svc)
        lines.append(f"  - {svc}: {desc}")

    # Warn about missing critical services
    missing = []
    if "sonarr" not in available_services:
        missing.append("TV show management (Sonarr not configured)")
    if "radarr" not in available_services:
        missing.append("movie management (Radarr not configured)")
    if missing:
        lines.append(f"\nNot available: {', '.join(missing)}.")

    return "\n".join(lines)
