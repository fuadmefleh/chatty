"""OpenAI gpt-image-1 image generation.

Always calls OpenAI directly regardless of CHAT_PROVIDER - image generation isn't
part of the LLMProvider abstraction (src/core/llm/), and OPENAI_API_KEY is
already a required env var per config.validate_config().
"""
import asyncio
import base64
import os
import uuid
from pathlib import Path

from openai import AsyncOpenAI

from src.core import config

_VALID_SIZES = {"auto", "1024x1024", "1536x1024", "1024x1536"}


def _chat_uploads_dir() -> Path:
    """Same uploads/chat directory chatty_web_server.py's _chat_uploads_dir()
    writes to and serves from - duplicated here (rather than imported) to
    avoid a circular import (chatty_web_server -> SkillsManager -> this
    module -> chatty_web_server), same reasoning as config.WEB_USER_ID's own
    docstring for why it's duplicated rather than imported."""
    d = config.MEMORY_DIR / config.WEB_USER_ID / "uploads" / "chat"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def generate_image(prompt: str, size: str = "auto") -> dict:
    if not config.OPENAI_API_KEY:
        return {"success": False, "error": "OPENAI_API_KEY is not configured"}
    if size not in _VALID_SIZES:
        size = "auto"

    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    response = await client.images.generate(model="gpt-image-1", prompt=prompt, size=size, n=1)
    image_bytes = base64.b64decode(response.data[0].b64_json)

    filename = f"{uuid.uuid4()}.png"
    await asyncio.to_thread((_chat_uploads_dir() / filename).write_bytes, image_bytes)

    # The image is embedded straight into the LLM's markdown reply with no React
    # component in the loop to attach an auth header, so the URL needs the shared
    # API key baked in as a query param - the same auth path chatty_web_server.py's
    # chat-media endpoint already accepts (mirrors websocket_chat's own `?api_key=`).
    api_key = os.getenv("CHATTY_WEB_API_KEY", "changeme")
    url = f"/api/chatty/chat-media/{filename}?api_key={api_key}"
    return {"success": True, "url": url}
