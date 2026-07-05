"""Anthropic Claude provider.

All the translation between chatty's OpenAI-shaped messages/tools/responses
and Anthropic's Messages API lives here - callers (StagedReACTAgent,
WebChatAgent) never branch on backend.

Key differences from OpenAI's wire format, handled below:
- System prompt is a top-level `system=` param, not a message.
- Tool schema uses `input_schema` instead of nested `function.parameters`.
- Tool-use responses are content blocks (`{"type":"tool_use", id, name, input}`)
  instead of `message.tool_calls`.
- Tool results must be sent back as a single `user` message with
  `content=[{"type":"tool_result", tool_use_id, content}, ...]` - all tool
  results for one turn batched together, not one `role:"tool"` message each.
- No native JSON-mode: a forced synthetic tool call was tried first, but a
  live test against the real API showed Claude inventing arbitrary wrapper
  keys around the payload (e.g. {"$PARAMETER_NAME": {...actual fields...}})
  when the tool's input_schema can't describe the caller's ad-hoc shape.
  Instead we append a plain instruction and strip markdown code fences,
  which Claude reliably honors - callers already tolerate stray
  non-JSON output via their own json.JSONDecodeError fallback paths.
- Streaming events are block-indexed (`content_block_delta` with
  `text_delta`/`input_json_delta`) rather than OpenAI's flatter per-chunk shape.
"""
import json
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from anthropic import (
    APIConnectionError,
    APITimeoutError,
    AsyncAnthropic,
    InternalServerError,
    OverloadedError,
    RateLimitError,
)

from src.core.token_usage_manager import get_token_usage_manager

from .base import LLMProvider
from .types import LLMResponse, LLMRetryableError, StreamChunk, ToolCall, ToolCallDelta, Usage

_RETRYABLE_ERRORS = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError, OverloadedError)

_JSON_MODE_SUFFIX = "\n\nRespond with ONLY the raw JSON object - no prose, no markdown code fences."


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text


def _split_system(messages: List[Dict]) -> Tuple[Optional[str], List[Dict]]:
    """Pull out system message(s) into Anthropic's top-level `system` param;
    join multiple with a blank line (web_chat_agent inserts up to 3)."""
    system_parts = [m["content"] for m in messages if m.get("role") == "system" and m.get("content")]
    rest = [m for m in messages if m.get("role") != "system"]
    system = "\n\n".join(system_parts) if system_parts else None
    return system, rest


def _to_anthropic_messages(messages: List[Dict]) -> List[Dict]:
    """Convert OpenAI-shaped (post-system-split) messages into Anthropic's
    message list, batching any run of trailing `role:"tool"` messages into
    one `user` message with `tool_result` content blocks."""
    out: List[Dict] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        role = msg.get("role")

        if role == "assistant":
            content: List[Dict] = []
            if msg.get("content"):
                content.append({"type": "text", "text": msg["content"]})
            for tc in msg.get("tool_calls") or []:
                fn = tc["function"]
                try:
                    tool_input = json.loads(fn["arguments"]) if fn.get("arguments") else {}
                except json.JSONDecodeError:
                    tool_input = {}
                content.append({
                    "type": "tool_use", "id": tc["id"], "name": fn["name"], "input": tool_input,
                })
            out.append({"role": "assistant", "content": content or msg.get("content") or ""})
            i += 1
            continue

        if role == "tool":
            tool_results = []
            while i < len(messages) and messages[i].get("role") == "tool":
                t = messages[i]
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": t["tool_call_id"],
                    "content": t.get("content") or "",
                })
                i += 1
            out.append({"role": "user", "content": tool_results})
            continue

        # user (and any other non-system role) pass through as plain text turns
        out.append({"role": "user" if role != "assistant" else role, "content": msg.get("content") or ""})
        i += 1

    return out


def _tools_to_anthropic(tools: Optional[List[Dict]]) -> Optional[List[Dict]]:
    if not tools:
        return None
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"].get("description", ""),
            "input_schema": t["function"].get("parameters", {"type": "object"}),
        }
        for t in tools
    ]


def _usage_from_message(message) -> Optional[Usage]:
    u = getattr(message, "usage", None)
    if u is None:
        return None
    input_tokens = getattr(u, "input_tokens", 0) or 0
    output_tokens = getattr(u, "output_tokens", 0) or 0
    return Usage(
        prompt_tokens=input_tokens, completion_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )


def _extract_response(message) -> LLMResponse:
    text_parts = []
    tool_calls = []
    for block in message.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=json.dumps(block.input)))
    return LLMResponse(
        content="".join(text_parts) if text_parts else None,
        tool_calls=tool_calls,
        stop_reason="tool_calls" if tool_calls else (message.stop_reason or "stop"),
        raw=message,
        usage=_usage_from_message(message),
    )


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.supports_temperature = True
        self.provider_label = "anthropic"

    def _record_usage(self, usage: Optional[Usage]) -> None:
        if usage is not None:
            get_token_usage_manager().record(
                provider=self.provider_label, model=self.model,
                prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens,
            )

    @property
    def supports_vision(self) -> bool:
        return True

    async def complete(
        self, messages: List[Dict], *, response_format: str = "text",
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        if response_format == "json":
            return await self._complete_json(messages, temperature=temperature)

        system, rest = _split_system(messages)
        kwargs: Dict[str, Any] = dict(
            model=self.model, max_tokens=4096, messages=_to_anthropic_messages(rest),
        )
        if system:
            kwargs["system"] = system
        if temperature is not None:
            kwargs["temperature"] = temperature
        try:
            message = await self.client.messages.create(**kwargs)
        except _RETRYABLE_ERRORS as e:
            raise LLMRetryableError(str(e)) from e
        response = _extract_response(message)
        self._record_usage(response.usage)
        return response

    async def _complete_json(self, messages: List[Dict], *, temperature: Optional[float]) -> LLMResponse:
        """No native JSON mode - append an instruction to the last user turn
        and strip markdown code fences from the reply. Callers already
        tolerate stray non-JSON output via their own json.JSONDecodeError
        fallback paths, so best-effort cleanup here is sufficient."""
        system, rest = _split_system(messages)
        anthropic_messages = _to_anthropic_messages(rest)
        if anthropic_messages and anthropic_messages[-1]["role"] == "user":
            last = dict(anthropic_messages[-1])
            if isinstance(last["content"], str):
                last["content"] = last["content"] + _JSON_MODE_SUFFIX
            else:
                last["content"] = list(last["content"]) + [{"type": "text", "text": _JSON_MODE_SUFFIX}]
            anthropic_messages = anthropic_messages[:-1] + [last]

        kwargs: Dict[str, Any] = dict(model=self.model, max_tokens=4096, messages=anthropic_messages)
        if system:
            kwargs["system"] = system
        if temperature is not None:
            kwargs["temperature"] = temperature
        try:
            message = await self.client.messages.create(**kwargs)
        except _RETRYABLE_ERRORS as e:
            raise LLMRetryableError(str(e)) from e

        text = "".join(b.text for b in message.content if b.type == "text")
        usage = _usage_from_message(message)
        self._record_usage(usage)
        return LLMResponse(content=_strip_json_fences(text), stop_reason="stop", raw=message, usage=usage)

    async def complete_with_tools(
        self, messages: List[Dict], tools: List[Dict], *,
        tool_choice: str = "auto", temperature: Optional[float] = None,
    ) -> LLMResponse:
        system, rest = _split_system(messages)
        kwargs: Dict[str, Any] = dict(
            model=self.model, max_tokens=4096, messages=_to_anthropic_messages(rest),
        )
        if system:
            kwargs["system"] = system
        anthropic_tools = _tools_to_anthropic(tools)
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools
            if tool_choice == "auto":
                kwargs["tool_choice"] = {"type": "auto"}
            elif tool_choice == "none":
                kwargs["tool_choice"] = {"type": "none"}
        if temperature is not None:
            kwargs["temperature"] = temperature
        try:
            message = await self.client.messages.create(**kwargs)
        except _RETRYABLE_ERRORS as e:
            raise LLMRetryableError(str(e)) from e
        response = _extract_response(message)
        self._record_usage(response.usage)
        return response

    async def stream_with_tools(
        self, messages: List[Dict], tools: List[Dict], *,
        tool_choice: str = "auto", temperature: Optional[float] = None,
    ) -> AsyncIterator[StreamChunk]:
        system, rest = _split_system(messages)
        kwargs: Dict[str, Any] = dict(
            model=self.model, max_tokens=4096, messages=_to_anthropic_messages(rest),
        )
        if system:
            kwargs["system"] = system
        anthropic_tools = _tools_to_anthropic(tools)
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools
            if tool_choice == "auto":
                kwargs["tool_choice"] = {"type": "auto"}
            elif tool_choice == "none":
                kwargs["tool_choice"] = {"type": "none"}
        if temperature is not None:
            kwargs["temperature"] = temperature

        block_index_to_name: Dict[int, str] = {}
        input_tokens = 0
        output_tokens = 0
        try:
            async with self.client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if event.type == "message_start":
                        usage = getattr(event.message, "usage", None)
                        if usage is not None:
                            input_tokens = getattr(usage, "input_tokens", 0) or 0
                    elif event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            block_index_to_name[event.index] = event.content_block.name
                            yield StreamChunk(tool_call_deltas=[
                                ToolCallDelta(index=event.index, id=event.content_block.id, name=event.content_block.name)
                            ])
                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            yield StreamChunk(text_delta=event.delta.text)
                        elif event.delta.type == "input_json_delta":
                            yield StreamChunk(tool_call_deltas=[
                                ToolCallDelta(index=event.index, arguments_delta=event.delta.partial_json)
                            ])
                    elif event.type == "message_delta":
                        stop_reason = getattr(event.delta, "stop_reason", None)
                        usage = getattr(event, "usage", None)
                        if usage is not None:
                            output_tokens = getattr(usage, "output_tokens", 0) or 0
                        if stop_reason:
                            yield StreamChunk(is_final=True, stop_reason=stop_reason)
        except _RETRYABLE_ERRORS as e:
            raise LLMRetryableError(str(e)) from e
        if input_tokens or output_tokens:
            self._record_usage(Usage(
                prompt_tokens=input_tokens, completion_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ))

    async def complete_vision(self, prompt: str, image_b64: str, *, max_tokens: int = 800) -> str:
        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}},
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
        except _RETRYABLE_ERRORS as e:
            raise LLMRetryableError(str(e)) from e
        self._record_usage(_usage_from_message(message))
        text_parts = [b.text for b in message.content if b.type == "text"]
        return "".join(text_parts)
