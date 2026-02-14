"""Tool/function calling schemas for LLM providers."""

from typing import Any, Dict, List

# Tool schema for parsing media commands
PARSE_MEDIA_COMMAND_SCHEMA = {
    "name": "parse_media_command",
    "description": "Extract structured intent from a natural language media management command",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["remove", "search", "add", "upgrade", "list", "info", "delete"],
                "description": "The action to perform. 'remove' or 'delete' = delete files, 'search' = search for media, 'add' = add to library, 'upgrade' = upgrade quality, 'list' = show items, 'info' = get details",
            },
            "media_type": {
                "type": "string",
                "enum": ["tv", "movie", "music", "audiobook"],
                "description": "Type of media: 'tv' for TV shows/series, 'movie' for films, 'music' for songs/albums, 'audiobook' for audio books",
            },
            "title": {
                "type": "string",
                "description": "The title of the TV show, movie, album, or audiobook. Extract the exact name mentioned.",
            },
            "season": {
                "type": "integer",
                "description": "Season number for TV shows only. Extract if mentioned (e.g., 'season 1' = 1).",
            },
            "episodes": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "List of episode numbers for TV shows. Extract all mentioned episodes (e.g., 'episodes 1 and 2' = [1, 2], 'episode 5' = [5]).",
            },
            "criteria": {
                "type": "object",
                "description": "Additional search/filter criteria as key-value pairs",
                "properties": {
                    "language": {
                        "type": "string",
                        "description": "Language code (e.g., 'en', 'es', 'fr') or description (e.g., 'English', 'all English')",
                    },
                    "quality": {
                        "type": "string",
                        "description": "Quality preference (e.g., '4K', '1080p', 'HD', 'BluRay')",
                    },
                    "year": {
                        "type": "integer",
                        "description": "Release year for disambiguation",
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


def get_system_prompt() -> str:
    """Get the system prompt for command parsing."""
    return """You are a media management assistant that extracts structured intent from natural language commands.

Your job is to parse user commands about managing their TV shows, movies, music, and audiobooks.

Key guidelines:
- Extract the ACTION (remove/delete, search, add, upgrade, list, info)
- Identify the MEDIA TYPE (tv, movie, music, audiobook)
- Extract the TITLE exactly as mentioned
- For TV shows, extract SEASON and EPISODE numbers if mentioned
- Extract any CRITERIA (language, quality, year, etc.)

Examples:
- "remove episode 1 and 2 of Angel season 1" → action=remove, media_type=tv, title="Angel", season=1, episodes=[1,2]
- "search for an all English version" → action=search, criteria={language: "English"}
- "add Breaking Bad to my library" → action=add, media_type=tv, title="Breaking Bad"
- "find 4K version of Blade Runner" → action=search, media_type=movie, title="Blade Runner", criteria={quality: "4K"}
- "show me all my TV shows" → action=list, media_type=tv

Always use the parse_media_command function to return structured data."""
