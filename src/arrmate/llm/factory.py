"""Factory for creating LLM provider instances."""

from typing import Dict, Type

from ..config.settings import settings
from .anthropic import AnthropicProvider
from .base import BaseLLMProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider

# Provider registry
_PROVIDERS: Dict[str, Type[BaseLLMProvider]] = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}


def register_provider(name: str, provider_class: Type[BaseLLMProvider]) -> None:
    """Register a custom LLM provider.

    Args:
        name: Provider name (used in configuration)
        provider_class: Provider class (must inherit from BaseLLMProvider)
    """
    _PROVIDERS[name] = provider_class


def create_llm_provider(provider_name: str | None = None) -> BaseLLMProvider:
    """Create an LLM provider instance based on configuration.

    Args:
        provider_name: Optional provider name override (defaults to settings.llm_provider)

    Returns:
        Configured LLM provider instance

    Raises:
        ValueError: If provider is not supported or configuration is invalid
    """
    provider_name = provider_name or settings.llm_provider

    if provider_name not in _PROVIDERS:
        available = ", ".join(_PROVIDERS.keys())
        raise ValueError(
            f"Unsupported LLM provider: {provider_name}. Available: {available}"
        )

    provider_class = _PROVIDERS[provider_name]

    # Create provider with appropriate configuration
    if provider_name == "ollama":
        return OllamaProvider(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
        )
    elif provider_name == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        return OpenAIProvider(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    elif provider_name == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Anthropic provider")
        return AnthropicProvider(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
        )
    else:
        # Custom provider - try to instantiate with default constructor
        return provider_class()
