"""OpenAI LLM provider implementation."""

import json
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from .base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider with function calling support."""

    def __init__(
        self,
        model: str = "gpt-4-turbo-preview",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """Initialize OpenAI provider.

        Args:
            model: OpenAI model to use
            api_key: OpenAI API key
            base_url: Optional custom base URL
        """
        super().__init__(model)
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    def supports_tool_calling(self) -> bool:
        """OpenAI supports function calling."""
        return True

    async def parse_command(
        self, user_input: str, tools: List[Dict[str, Any]], system_prompt: str
    ) -> Dict[str, Any]:
        """Parse command using OpenAI with function calling.

        Args:
            user_input: User's natural language command
            tools: Tool schemas for function calling
            system_prompt: System prompt

        Returns:
            Parsed parameters from function call

        Raises:
            ValueError: If parsing fails
        """
        try:
            # OpenAI function calling format
            openai_tools = [{"type": "function", "function": tool} for tool in tools]

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                tools=openai_tools,
                tool_choice="auto",
            )

            message = response.choices[0].message

            if not message.tool_calls:
                raise ValueError("LLM did not use the parse_media_command function")

            # Get the first tool call
            tool_call = message.tool_calls[0]
            function_args = json.loads(tool_call.function.arguments)

            if not function_args:
                raise ValueError("No arguments returned from function call")

            return function_args

        except Exception as e:
            raise ValueError(f"Failed to parse command with OpenAI: {str(e)}") from e

    async def generate_response(
        self, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a response using OpenAI.

        Args:
            prompt: The prompt to respond to
            context: Optional context

        Returns:
            Generated response
        """
        messages = []

        if context:
            messages.append(
                {
                    "role": "system",
                    "content": f"Context: {json.dumps(context)}",
                }
            )

        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )

        return response.choices[0].message.content or ""

    async def close(self) -> None:
        """Close the OpenAI client."""
        await self.client.close()
