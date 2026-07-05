"""LLM provider interface."""
from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, List, Optional

from .types import LLMResponse, StreamChunk


class LLMProvider(ABC):
    """Answers chat completions for both the Telegram bot (StagedReACTAgent)
    and the web dashboard (WebChatAgent). Implementations translate between
    this normalized interface and their own SDK/wire format; callers always
    speak OpenAI-shaped messages and tool schemas regardless of backend."""

    model: str

    @abstractmethod
    async def complete(
        self, messages: List[Dict], *, response_format: str = "text",
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Single-turn/multi-message completion, no tools."""

    @abstractmethod
    async def complete_with_tools(
        self, messages: List[Dict], tools: List[Dict], *,
        tool_choice: str = "auto", temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Non-streaming tool-calling turn. `tools` is OpenAI function-calling
        schema, as produced by SkillsManager.get_openai_tools()."""

    @abstractmethod
    def stream_with_tools(
        self, messages: List[Dict], tools: List[Dict], *,
        tool_choice: str = "auto", temperature: Optional[float] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Streaming tool-calling turn."""

    @property
    @abstractmethod
    def supports_vision(self) -> bool:
        ...

    @abstractmethod
    async def complete_vision(self, prompt: str, image_b64: str, *, max_tokens: int = 800) -> str:
        """Single-turn text+image completion."""
