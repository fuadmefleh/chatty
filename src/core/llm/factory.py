"""Factory for selecting the configured LLM backend."""
from typing import Optional

from src.core import config

from .base import LLMProvider
from .openai_provider import OpenAIProvider

_provider_singleton: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    global _provider_singleton
    if _provider_singleton is None:
        if config.CHAT_PROVIDER == "anthropic":
            from .anthropic_provider import AnthropicProvider
            _provider_singleton = AnthropicProvider(
                api_key=config.ANTHROPIC_API_KEY, model=config.ANTHROPIC_MODEL
            )
        elif config.CHAT_PROVIDER == "local":
            _provider_singleton = OpenAIProvider(
                api_key="not-needed", base_url=config.LOCAL_LLM_BASE_URL,
                model=config.LOCAL_LLM_MODEL, supports_vision=False,
            )
        else:
            _provider_singleton = OpenAIProvider(
                api_key=config.OPENAI_API_KEY, base_url=None,
                model=config.OPENAI_MODEL, supports_vision=True,
            )
    return _provider_singleton
