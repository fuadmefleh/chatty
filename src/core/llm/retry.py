"""Provider-agnostic retry helper for transient LLM errors."""
import asyncio
from typing import Awaitable, Callable, Optional, TypeVar

from .types import LLMRetryableError

T = TypeVar("T")

MAX_LLM_RETRIES = 2
RETRY_BASE_DELAY = 1.0  # seconds; doubles each retry


async def with_retries(
    coro_factory: Callable[[], Awaitable[T]], *,
    max_retries: int = MAX_LLM_RETRIES, base_delay: float = RETRY_BASE_DELAY,
    logger: Optional[object] = None,
) -> T:
    """Call coro_factory(), retrying on LLMRetryableError with exponential
    backoff. Providers are responsible for translating their own SDK
    exceptions (RateLimitError, APIConnectionError, etc.) into
    LLMRetryableError before it escapes complete()/complete_with_tools()."""
    last_exc: Optional[LLMRetryableError] = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except LLMRetryableError as e:
            last_exc = e
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                if logger:
                    logger.warning(
                        f"Transient LLM error ({type(e.__cause__ or e).__name__}), retrying in "
                        f"{delay}s (attempt {attempt + 1}/{max_retries})"
                    )
                await asyncio.sleep(delay)
            else:
                if logger:
                    logger.error(f"Exhausted retries after {max_retries} attempts: {e}")
    raise last_exc
