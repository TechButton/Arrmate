"""Anthropic (Claude) LLM provider implementation."""

import json
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic

from .base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude LLM provider with tool use support."""

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        api_key: Optional[str] = None,
    ) -> None:
        """Initialize Anthropic provider.

        Args:
            model: Claude model to use
            api_key: Anthropic API key
        """
        super().__init__(model)
        self.client = AsyncAnthropic(api_key=api_key)

    def supports_tool_calling(self) -> bool:
        """Anthropic supports tool use."""
        return True

    async def parse_command(
        self, user_input: str, tools: List[Dict[str, Any]], system_prompt: str
    ) -> Dict[str, Any]:
        """Parse command using Claude with tool use.

        Args:
            user_input: User's natural language command
            tools: Tool schemas for tool use
            system_prompt: System prompt

        Returns:
            Parsed parameters from tool use

        Raises:
            ValueError: If parsing fails
        """
        try:
            # Anthropic tool format
            anthropic_tools = [
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool["parameters"],
                }
                for tool in tools
            ]

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_input}],
                tools=anthropic_tools,
            )

            # Extract tool use from response
            tool_use_block = None
            for block in response.content:
                if block.type == "tool_use":
                    tool_use_block = block
                    break

            if not tool_use_block:
                raise ValueError("Claude did not use the parse_media_command tool")

            function_args = tool_use_block.input

            if not function_args:
                raise ValueError("No input returned from tool use")

            return function_args

        except Exception as e:
            raise ValueError(f"Failed to parse command with Anthropic: {str(e)}") from e

    async def generate_response(
        self, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a response using Claude.

        Args:
            prompt: The prompt to respond to
            context: Optional context

        Returns:
            Generated response
        """
        system_content = ""
        if context:
            system_content = f"Context: {json.dumps(context)}"

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_content if system_content else None,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from response
        text_content = ""
        for block in response.content:
            if hasattr(block, "text"):
                text_content += block.text

        return text_content

    async def close(self) -> None:
        """Close the Anthropic client."""
        await self.client.close()
