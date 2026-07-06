"""Tests for the image_generation skill (OpenAI gpt-image-1), always called
directly regardless of CHAT_PROVIDER - see skills/image_generation/image_api.py."""
import base64
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import config
import skills.image_generation.tools as tools_module

# tools.py loads image_api.py via importlib.util as a standalone module
# (see docs/ARCHITECTURE.md's "Explicit imports" convention) - grab that same
# instance so patches on it (e.g. AsyncOpenAI) are visible to GenerateImageTool.
_image_api = tools_module._image_api


@pytest.fixture(autouse=True)
def isolated_uploads(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(config, "WEB_USER_ID", "web_user")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    yield


def _fake_openai_client(image_bytes: bytes):
    response = MagicMock()
    response.data = [MagicMock(b64_json=base64.b64encode(image_bytes).decode("ascii"))]
    client = MagicMock()
    client.images.generate = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_generate_image_writes_file_and_returns_url(monkeypatch):
    client = _fake_openai_client(b"fake-png-bytes")
    monkeypatch.setattr(_image_api, "AsyncOpenAI", lambda api_key: client)
    monkeypatch.setenv("CHATTY_WEB_API_KEY", "shared-secret")

    result = await _image_api.generate_image("a cat astronaut", size="1024x1024")

    assert result["success"] is True
    assert result["url"].startswith("/api/chatty/chat-media/")
    assert "api_key=shared-secret" in result["url"]

    filename = result["url"].split("/")[-1].split("?")[0]
    stored = _image_api._chat_uploads_dir() / filename
    assert stored.read_bytes() == b"fake-png-bytes"

    client.images.generate.assert_awaited_once_with(
        model="gpt-image-1", prompt="a cat astronaut", size="1024x1024", n=1
    )


@pytest.mark.asyncio
async def test_generate_image_invalid_size_falls_back_to_auto(monkeypatch):
    client = _fake_openai_client(b"bytes")
    monkeypatch.setattr(_image_api, "AsyncOpenAI", lambda api_key: client)

    await _image_api.generate_image("a dog", size="not-a-real-size")

    assert client.images.generate.await_args.kwargs["size"] == "auto"


@pytest.mark.asyncio
async def test_generate_image_missing_api_key_returns_error(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", None)
    result = await _image_api.generate_image("a dog")
    assert result["success"] is False
    assert "OPENAI_API_KEY" in result["error"]


@pytest.mark.asyncio
async def test_generate_image_tool_wraps_result_as_json(monkeypatch):
    client = _fake_openai_client(b"bytes")
    monkeypatch.setattr(_image_api, "AsyncOpenAI", lambda api_key: client)

    tool = tools_module.GenerateImageTool()
    result = json.loads(await tool.execute(prompt="a robot"))

    assert result["success"] is True
    assert result["url"].startswith("/api/chatty/chat-media/")


@pytest.mark.asyncio
async def test_generate_image_tool_catches_exceptions(monkeypatch):
    client = MagicMock()
    client.images.generate = AsyncMock(side_effect=RuntimeError("rate limited"))
    monkeypatch.setattr(_image_api, "AsyncOpenAI", lambda api_key: client)

    tool = tools_module.GenerateImageTool()
    result = json.loads(await tool.execute(prompt="a robot"))

    assert result["success"] is False
    assert "rate limited" in result["error"]
