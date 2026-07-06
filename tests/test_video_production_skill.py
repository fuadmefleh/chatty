"""Tests for the video_production skill (OpenMontage API wrapper)."""
import json
import sys
from pathlib import Path


import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import config
import skills.video_production.tools as tools_module

# tools.py loads video_api.py via importlib.util — grab the same instance
# so our patches are visible to GenerateVideoTool.
_video_api = tools_module._video_api


class _FakeResponse:
    """Minimal stand-in for aiohttp.ClientResponse used as an async context manager."""

    def __init__(
        self,
        status=200,
        json_data=None,
        text_data="",
        read_data=b"",
    ):
        self.status = status
        self._json_data = json_data
        self._text_data = text_data
        self._read_data = read_data

    async def json(self):
        return self._json_data

    async def text(self):
        return self._text_data

    async def read(self):
        return self._read_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class _FakeSession:
    """Minimal stand-in for aiohttp.ClientSession.

    ``calls`` is a list of (method, url, kwargs) tuples for inspection.
    ``_call_index`` is incremented on each call so you can sequence responses
    (e.g. submit -> poll-1 -> poll-2 -> download) without checking URLs.
    """

    def __init__(self, responder):
        self._responder = responder
        self.calls = []
        self._call_index = 0

    def post(self, url, **kwargs):
        idx = self._call_index
        self._call_index += 1
        self.calls.append(("POST", url, kwargs))
        return self._responder("POST", url, kwargs, idx)

    def get(self, url, **kwargs):
        idx = self._call_index
        self._call_index += 1
        self.calls.append(("GET", url, kwargs))
        return self._responder("GET", url, kwargs, idx)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


def _patch_session(monkeypatch, responder):
    fake_session = _FakeSession(responder)
    monkeypatch.setattr(_video_api.aiohttp, "ClientSession", lambda *a, **kw: fake_session)
    return fake_session


@pytest.fixture(autouse=True)
def isolated_uploads(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(config, "WEB_USER_ID", "web_user")
    monkeypatch.setattr(config, "OPENMONTAGE_API_KEY", "om-test-key")
    monkeypatch.setattr(config, "OPENMONTAGE_API_URL", "https://api.openmontage.ai")
    yield


# -- generate_video happy path --


async def test_generate_video_happy_path(monkeypatch):
    def responder(method, url, kwargs, idx):
        if method == "POST":
            assert url.endswith("/v1/generate")
            assert kwargs["json"]["prompt"] == "a cat astronaut"
            return _FakeResponse(status=202, json_data={"job_id": "job-abc"})
        # First GET -> still processing, second GET -> completed
        if idx == 0:
            return _FakeResponse(
                status=200,
                json_data={"status": "processing", "progress": 0.3},
            )
        if idx == 1:
            return _FakeResponse(
                status=200,
                json_data={
                    "status": "completed",
                    "download_url": "/v1/jobs/job-abc/download",
                },
            )
        # download
        return _FakeResponse(status=200, read_data=b"fake-mp4-bytes")

    _patch_session(monkeypatch, responder)

    result = await _video_api.generate_video("a cat astronaut")

    assert result["success"] is True
    assert result["url"].startswith("/api/chatty/chat-media/")
    assert "api_key=" in result["url"]
    assert result["duration_seconds"] == 4
    assert result["resolution"] == "auto"

    # Verify the file was written
    filename = result["url"].split("/")[-1].split("?")[0]
    stored = _video_api._chat_uploads_dir() / filename
    assert stored.read_bytes() == b"fake-mp4-bytes"


# -- immediate completion (zero polling) --


async def test_generate_video_immediate_completion(monkeypatch):
    def responder(method, url, kwargs, idx):
        if method == "POST":
            return _FakeResponse(status=202, json_data={"job_id": "job-x"})
        return _FakeResponse(
            status=200,
            json_data={
                "status": "completed",
                "download_url": "/v1/jobs/job-x/download",
            },
        )

    _patch_session(monkeypatch, responder)

    result = await _video_api.generate_video("sunset timelapse", duration_seconds=8)

    assert result["success"] is True
    assert result["duration_seconds"] == 8


# -- missing API key --


async def test_generate_video_missing_api_key(monkeypatch):
    monkeypatch.setattr(config, "OPENMONTAGE_API_KEY", None)
    result = await _video_api.generate_video("something")
    assert result["success"] is False
    assert "OPENMONTAGE_API_KEY" in result["error"]


# -- submission failure --


async def test_generate_video_submission_failure(monkeypatch):
    def responder(method, url, kwargs, idx):
        return _FakeResponse(status=403, text_data="Invalid API key")

    _patch_session(monkeypatch, responder)

    result = await _video_api.generate_video("something")

    assert result["success"] is False
    assert "403" in result["error"]
    assert "Invalid API key" in result["error"]


# -- job failure --


async def test_generate_video_job_failed(monkeypatch):
    def responder(method, url, kwargs, idx):
        if method == "POST":
            return _FakeResponse(status=202, json_data={"job_id": "job-fail"})
        return _FakeResponse(
            status=200,
            json_data={"status": "failed", "error": "generation pipeline error"},
        )

    _patch_session(monkeypatch, responder)

    with pytest.raises(RuntimeError, match="generation pipeline error"):
        await _video_api.generate_video("something")


# -- duration clamping --


async def test_generate_video_duration_clamped(monkeypatch):
    def responder(method, url, kwargs, idx):
        if method == "POST":
            # 9 is equidistant from 8 and 10; min() picks first in set order (8)
            assert kwargs["json"]["duration_seconds"] == 8
            return _FakeResponse(status=202, json_data={"job_id": "job-clamp"})
        return _FakeResponse(
            status=200,
            json_data={
                "status": "completed",
                "download_url": "/v1/jobs/job-clamp/download",
            },
        )

    _patch_session(monkeypatch, responder)

    result = await _video_api.generate_video("test", duration_seconds=9)
    assert result["duration_seconds"] == 8


async def test_generate_video_invalid_resolution_defaults_to_auto(monkeypatch):
    def responder(method, url, kwargs, idx):
        if method == "POST":
            assert kwargs["json"]["resolution"] == "auto"
            return _FakeResponse(status=202, json_data={"job_id": "job-res"})
        return _FakeResponse(
            status=200,
            json_data={
                "status": "completed",
                "download_url": "/v1/jobs/job-res/download",
            },
        )

    _patch_session(monkeypatch, responder)

    result = await _video_api.generate_video("test", resolution="4k")
    assert result["resolution"] == "auto"


# -- GenerateVideoTool wrapper --


async def test_generate_video_tool_returns_json(monkeypatch):
    def responder(method, url, kwargs, idx):
        if method == "POST":
            return _FakeResponse(status=202, json_data={"job_id": "job-tool"})
        return _FakeResponse(
            status=200,
            json_data={
                "status": "completed",
                "download_url": "/v1/jobs/job-tool/download",
            },
        )

    _patch_session(monkeypatch, responder)

    tool = tools_module.GenerateVideoTool()
    result = json.loads(await tool.execute(prompt="a robot dancing"))

    assert result["success"] is True
    assert "url" in result


async def test_generate_video_tool_catches_exceptions(monkeypatch):
    def responder(method, url, kwargs, idx):
        raise RuntimeError("network error")

    _patch_session(monkeypatch, responder)

    tool = tools_module.GenerateVideoTool()
    result = json.loads(await tool.execute(prompt="something"))

    assert result["success"] is False
    assert "network error" in result["error"]


async def test_generate_video_tool_accepts_all_params(monkeypatch):
    def responder(method, url, kwargs, idx):
        if method == "POST":
            assert kwargs["json"]["duration_seconds"] == 15
            assert kwargs["json"]["resolution"] == "1080p"
            return _FakeResponse(status=202, json_data={"job_id": "job-full"})
        return _FakeResponse(
            status=200,
            json_data={
                "status": "completed",
                "download_url": "/v1/jobs/job-full/download",
            },
        )

    _patch_session(monkeypatch, responder)

    tool = tools_module.GenerateVideoTool()
    result = json.loads(
        await tool.execute(
            prompt="epic scene",
            duration_seconds=15,
            resolution="1080p",
        )
    )

    assert result["success"] is True
    assert result["duration_seconds"] == 15
    assert result["resolution"] == "1080p"


# -- tool has required attributes --


def test_tool_has_required_attributes():
    tool = tools_module.GenerateVideoTool()
    assert tool.name == "generate_video"
    assert tool.parameters["type"] == "object"
    assert tool.parameters["required"] == ["prompt"]
    assert "prompt" in tool.parameters["properties"]
