"""Normalized types shared by all LLM providers.

Messages passed into/out of providers stay plain `List[Dict]` in OpenAI's
existing shape ({"role","content","tool_calls","tool_call_id",...}) - that's
the one wire format the rest of the codebase speaks. Each provider
translates at its own boundary only (see anthropic_provider.py for the
non-trivial case); callers never branch on backend.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class LLMRetryableError(Exception):
    """Raised by a provider to signal a transient error (rate limit,
    connection, timeout, 5xx) worth retrying with backoff. Providers catch
    their own SDK-specific exceptions and re-raise this so retry logic stays
    provider-agnostic."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string, same contract as OpenAI's tool_calls

    def to_openai_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.arguments},
        }


@dataclass
class LLMResponse:
    content: Optional[str]
    tool_calls: List[ToolCall] = field(default_factory=list)
    stop_reason: str = "stop"
    raw: Any = None  # escape hatch for debug logging only

    def to_openai_message(self) -> Dict[str, Any]:
        msg: Dict[str, Any] = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = [tc.to_openai_dict() for tc in self.tool_calls]
        return msg


@dataclass
class ToolCallDelta:
    index: int
    id: Optional[str] = None
    name: Optional[str] = None
    arguments_delta: str = ""


@dataclass
class StreamChunk:
    text_delta: str = ""
    tool_call_deltas: List[ToolCallDelta] = field(default_factory=list)
    is_final: bool = False
    stop_reason: Optional[str] = None
