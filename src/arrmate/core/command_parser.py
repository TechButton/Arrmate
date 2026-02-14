"""Natural language command parser using LLM."""

from typing import Dict

from ..llm.base import BaseLLMProvider
from ..llm.factory import create_llm_provider
from ..llm.schemas import get_system_prompt, get_tool_schemas
from .models import Intent


class CommandParser:
    """Parses natural language commands into structured Intent objects."""

    def __init__(self, llm_provider: BaseLLMProvider | None = None) -> None:
        """Initialize the command parser.

        Args:
            llm_provider: Optional LLM provider (creates default if not provided)
        """
        self.llm_provider = llm_provider or create_llm_provider()

    async def parse(self, user_input: str) -> Intent:
        """Parse a natural language command into structured intent.

        Args:
            user_input: User's natural language command

        Returns:
            Parsed Intent object

        Raises:
            ValueError: If parsing fails or intent is invalid
        """
        # Get tool schemas and system prompt
        tools = get_tool_schemas()
        system_prompt = get_system_prompt()

        # Use LLM to extract structured intent
        try:
            parsed_data = await self.llm_provider.parse_command(
                user_input, tools, system_prompt
            )
        except Exception as e:
            raise ValueError(f"Failed to parse command: {str(e)}") from e

        # Validate and create Intent object
        try:
            intent = Intent(**parsed_data)
        except Exception as e:
            raise ValueError(f"Invalid intent extracted: {str(e)}") from e

        return intent

    async def close(self) -> None:
        """Clean up resources."""
        if self.llm_provider:
            await self.llm_provider.close()
