"""OpenAI-compatible provider - backs both "openai" and "local" CHAT_PROVIDER
values, since a local OpenAI-compatible server (e.g. llama.cpp) speaks the
exact same wire format."""
from typing import AsyncIterator, Dict, List, Optional

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)

from src.core.token_usage_manager import get_token_usage_manager

from .base import LLMProvider
from .types import LLMResponse, LLMRetryableError, StreamChunk, ToolCall, ToolCallDelta, Usage

_RETRYABLE_ERRORS = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)
_UNSUPPORTED_TEMP_MODELS = ("o1", "o3", "gpt-5")


def _usage_from_response(response) -> Optional[Usage]:
    u = getattr(response, "usage", None)
    if u is None:
        return None
    return Usage(
        prompt_tokens=u.prompt_tokens or 0,
        completion_tokens=u.completion_tokens or 0,
        total_tokens=u.total_tokens or 0,
    )


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: Optional[str], model: str, supports_vision: bool = True):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        # o1, o1-mini, o3-mini, and some newer OpenAI models reject a custom temperature
        self.supports_temperature = not any(x in model.lower() for x in _UNSUPPORTED_TEMP_MODELS)
        self._supports_vision = supports_vision
        # A local OpenAI-compatible server is reached via base_url; the hosted API isn't.
        self.provider_label = "local" if base_url else "openai"

    def _record_usage(self, usage: Optional[Usage]) -> None:
        if usage is not None:
            get_token_usage_manager().record(
                provider=self.provider_label, model=self.model,
                prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens,
            )

    @property
    def supports_vision(self) -> bool:
        return self._supports_vision

    def _temperature_kwargs(self, temperature: Optional[float]) -> Dict:
        if temperature is not None and self.supports_temperature:
            return {"temperature": temperature}
        return {}

    async def complete(
        self, messages: List[Dict], *, response_format: str = "text",
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        kwargs = dict(model=self.model, messages=messages, **self._temperature_kwargs(temperature))
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = await self.client.chat.completions.create(**kwargs)
        except _RETRYABLE_ERRORS as e:
            raise LLMRetryableError(str(e)) from e
        message = response.choices[0].message
        usage = _usage_from_response(response)
        self._record_usage(usage)
        return LLMResponse(
            content=message.content or "",
            stop_reason=response.choices[0].finish_reason or "stop",
            raw=response,
            usage=usage,
        )

    async def complete_with_tools(
        self, messages: List[Dict], tools: List[Dict], *,
        tool_choice: str = "auto", temperature: Optional[float] = None,
    ) -> LLMResponse:
        kwargs = dict(model=self.model, messages=messages, **self._temperature_kwargs(temperature))
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        try:
            response = await self.client.chat.completions.create(**kwargs)
        except _RETRYABLE_ERRORS as e:
            raise LLMRetryableError(str(e)) from e
        message = response.choices[0].message
        tool_calls = [
            ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments or "{}")
            for tc in (message.tool_calls or [])
        ]
        usage = _usage_from_response(response)
        self._record_usage(usage)
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            stop_reason="tool_calls" if tool_calls else (response.choices[0].finish_reason or "stop"),
            raw=response,
            usage=usage,
        )

    async def stream_with_tools(
        self, messages: List[Dict], tools: List[Dict], *,
        tool_choice: str = "auto", temperature: Optional[float] = None,
    ) -> AsyncIterator[StreamChunk]:
        kwargs = dict(
            model=self.model, messages=messages, stream=True,
            stream_options={"include_usage": True}, **self._temperature_kwargs(temperature),
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        try:
            stream = await self.client.chat.completions.create(**kwargs)
            async with stream:
                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        # The final chunk with `include_usage` has no choices, just usage.
                        self._record_usage(_usage_from_response(chunk))
                        continue
                    tool_call_deltas = []
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            tool_call_deltas.append(ToolCallDelta(
                                index=tc.index,
                                id=tc.id,
                                name=tc.function.name if tc.function else None,
                                arguments_delta=(tc.function.arguments or "") if tc.function else "",
                            ))
                    finish_reason = chunk.choices[0].finish_reason if chunk.choices else None
                    yield StreamChunk(
                        text_delta=delta.content or "",
                        tool_call_deltas=tool_call_deltas,
                        is_final=finish_reason is not None,
                        stop_reason=finish_reason,
                    )
        except _RETRYABLE_ERRORS as e:
            raise LLMRetryableError(str(e)) from e

    async def complete_vision(self, prompt: str, image_b64: str, *, max_tokens: int = 800) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    ],
                }],
                max_tokens=max_tokens,
            )
        except _RETRYABLE_ERRORS as e:
            raise LLMRetryableError(str(e)) from e
        self._record_usage(_usage_from_response(response))
        return response.choices[0].message.content or ""
