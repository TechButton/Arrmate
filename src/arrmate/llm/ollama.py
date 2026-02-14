"""Ollama LLM provider implementation."""

import json
from typing import Any, Dict, List, Optional

import ollama

from .base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Ollama LLM provider with tool calling support."""

    def __init__(
        self,
        model: str = "llama3.1:latest",
        base_url: str = "http://localhost:11434",
    ) -> None:
        """Initialize Ollama provider.

        Args:
            model: Ollama model to use (must support tool calling, e.g., llama3.1, mistral)
            base_url: Ollama server base URL
        """
        super().__init__(model)
        self.base_url = base_url
        self.client = ollama.Client(host=base_url)

    def supports_tool_calling(self) -> bool:
        """Ollama supports tool calling with compatible models."""
        return True

    async def parse_command(
        self, user_input: str, tools: List[Dict[str, Any]], system_prompt: str
    ) -> Dict[str, Any]:
        """Parse command using Ollama with tool calling.

        Args:
            user_input: User's natural language command
            tools: Tool schemas for function calling
            system_prompt: System prompt

        Returns:
            Parsed parameters from tool call

        Raises:
            ValueError: If parsing fails
        """
        try:
            # Ollama tool calling format
            ollama_tools = [
                {
                    "type": "function",
                    "function": tool,
                }
                for tool in tools
            ]

            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                tools=ollama_tools,
            )

            # Extract tool call from response
            message = response.get("message", {})
            tool_calls = message.get("tool_calls", [])

            if not tool_calls:
                raise ValueError("LLM did not use the parse_media_command function")

            # Get the first tool call (should be parse_media_command)
            tool_call = tool_calls[0]
            function_args = tool_call.get("function", {}).get("arguments", {})

            if not function_args:
                raise ValueError("No arguments returned from tool call")

            return function_args

        except Exception as e:
            raise ValueError(f"Failed to parse command with Ollama: {str(e)}") from e

    async def generate_response(
        self, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a response using Ollama.

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

        response = self.client.chat(
            model=self.model,
            messages=messages,
        )

        return response.get("message", {}).get("content", "")
