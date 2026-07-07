"""Text embeddings for long-term memory facts.

Always uses real OpenAI's embeddings API via config.OPENAI_API_KEY directly
(never config.CHAT_API_KEY/CHAT_BASE_URL, which may point at a local or
Anthropic provider that doesn't serve this endpoint) - mirrors
src/core/memory.py's consolidate_text() client construction pattern, minus
the base_url override.
"""
from typing import List

from openai import AsyncOpenAI

from src.core import config


async def get_embedding(text: str) -> List[float]:
    """Return the embedding vector for `text` using config.EMBEDDING_MODEL."""
    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    response = await client.embeddings.create(model=config.EMBEDDING_MODEL, input=text)
    return response.data[0].embedding
