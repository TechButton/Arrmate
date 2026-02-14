"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, model: Optional[str] = None) -> None:
        """Initialize the provider with optional model override.

        Args:
            model: Model name to use (provider-specific)
        """
        self.model = model

    @abstractmethod
    async def parse_command(
        self, user_input: str, tools: List[Dict[str, Any]], system_prompt: str
    ) -> Dict[str, Any]:
        """Parse a natural language command using tool calling.

        Args:
            user_input: The user's natural language command
            tools: List of tool/function schemas
            system_prompt: System prompt for the LLM

        Returns:
            Dictionary with parsed intent parameters

        Raises:
            ValueError: If parsing fails or LLM doesn't use tools correctly
        """
        pass

    @abstractmethod
    async def generate_response(
        self, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a natural language response.

        Args:
            prompt: The prompt to respond to
            context: Optional context dictionary

        Returns:
            Generated response text
        """
        pass

    @abstractmethod
    def supports_tool_calling(self) -> bool:
        """Check if this provider supports native tool/function calling.

        Returns:
            True if tool calling is supported, False otherwise
        """
        pass

    async def close(self) -> None:
        """Clean up any resources.

        Override this if your provider needs cleanup.
        """
        pass
