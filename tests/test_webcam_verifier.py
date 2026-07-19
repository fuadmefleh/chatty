"""Tests for src/managers/webcam_verifier.py - the per-kind playability
checks used to gate saving/approving webcam sources and by the periodic
health-check job. All httpx calls are mocked; no real network access."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers import webcam_verifier as wv


class FakeResponse:
    def __init__(self, status_code=200, headers=None, text="", content=b""):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text
        self._content = content

    async def aiter_bytes(self):
        yield self._content


class RaisingStream:
    """An async-iterable that yields one chunk then raises a ReadTimeout -
    simulates a live MJPEG stream that never closes on its own."""

    def __init__(self, first_chunk: bytes, raise_on_empty=False):
        self._first_chunk = first_chunk
        self._raise_on_empty = raise_on_empty

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        if self._first_chunk:
            yield self._first_chunk
        raise httpx.ReadTimeout("simulated timeout", request=None)


class FakeStreamResponse(FakeResponse):
    def __init__(self, aiter_bytes_obj=None, **kwargs):
        super().__init__(**kwargs)
        self._aiter_bytes_obj = aiter_bytes_obj

    def aiter_bytes(self):
        return self._aiter_bytes_obj


class FakeStreamCtx:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *args):
        return False


def make_client(get_return=None, get_side_effect=None, stream_return=None):
    client = MagicMock()
    if get_side_effect is not None:
        client.get = AsyncMock(side_effect=get_side_effect)
    else:
        client.get = AsyncMock(return_value=get_return)
    if stream_return is not None:
        client.stream = MagicMock(return_value=FakeStreamCtx(stream_return))
    return client


@pytest.mark.asyncio
async def test_verify_snapshot_ok():
    client = make_client(get_return=FakeResponse(200, {"content-type": "image/jpeg"}))
    result = await wv.verify_webcam("https://cam.example/snap.jpg", "snapshot", client=client)
    assert result.ok is True
    assert result.status == "ok"


@pytest.mark.asyncio
async def test_verify_snapshot_wrong_content_type():
    client = make_client(get_return=FakeResponse(200, {"content-type": "text/html"}))
    result = await wv.verify_webcam("https://cam.example/snap.jpg", "snapshot", client=client)
    assert result.ok is False
    assert "content-type" in result.detail.lower() or "image" in result.detail.lower()


@pytest.mark.asyncio
async def test_verify_snapshot_http_error():
    client = make_client(get_return=FakeResponse(404))
    result = await wv.verify_webcam("https://cam.example/snap.jpg", "snapshot", client=client)
    assert result.ok is False
    assert result.status == "unreachable"


@pytest.mark.asyncio
async def test_verify_mjpeg_ok_on_timeout_after_data():
    stream_resp = FakeStreamResponse(
        headers={"content-type": "multipart/x-mixed-replace; boundary=frame"},
        aiter_bytes_obj=RaisingStream(b"some jpeg bytes"),
    )
    client = make_client(stream_return=stream_resp)
    result = await wv.verify_webcam("https://cam.example/stream", "mjpeg", client=client)
    assert result.ok is True


@pytest.mark.asyncio
async def test_verify_mjpeg_wrong_content_type():
    stream_resp = FakeStreamResponse(headers={"content-type": "text/html"})
    client = make_client(stream_return=stream_resp)
    result = await wv.verify_webcam("https://cam.example/stream", "mjpeg", client=client)
    assert result.ok is False


@pytest.mark.asyncio
async def test_verify_mjpeg_no_data_before_timeout():
    stream_resp = FakeStreamResponse(
        headers={"content-type": "multipart/x-mixed-replace; boundary=frame"},
        aiter_bytes_obj=RaisingStream(b"", raise_on_empty=True),
    )
    client = make_client(stream_return=stream_resp)
    result = await wv.verify_webcam("https://cam.example/stream", "mjpeg", client=client)
    assert result.ok is False


@pytest.mark.asyncio
async def test_verify_hls_media_playlist_ok():
    client = make_client(get_return=FakeResponse(200, text="#EXTM3U\n#EXTINF:10,\nseg1.ts\n"))
    result = await wv.verify_webcam("https://cam.example/stream.m3u8", "hls", client=client)
    assert result.ok is True


@pytest.mark.asyncio
async def test_verify_hls_master_playlist_resolves_variant():
    master = FakeResponse(200, text="#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=100\nvariant.m3u8\n")
    variant = FakeResponse(200, text="#EXTM3U\n#EXTINF:10,\nseg1.ts\n")
    client = make_client(get_side_effect=[master, variant])
    result = await wv.verify_webcam("https://cam.example/master.m3u8", "hls", client=client)
    assert result.ok is True
    assert client.get.call_count == 2


@pytest.mark.asyncio
async def test_verify_hls_not_a_playlist():
    client = make_client(get_return=FakeResponse(200, text="<html>not m3u8</html>"))
    result = await wv.verify_webcam("https://cam.example/stream.m3u8", "hls", client=client)
    assert result.ok is False


@pytest.mark.asyncio
async def test_verify_youtube_ok():
    client = make_client(get_return=FakeResponse(200))
    result = await wv.verify_webcam("https://www.youtube.com/watch?v=abc123def", "youtube", client=client)
    assert result.ok is True


@pytest.mark.asyncio
async def test_verify_youtube_embedding_disabled():
    client = make_client(get_return=FakeResponse(401))
    result = await wv.verify_webcam("https://youtu.be/abc123def", "youtube", client=client)
    assert result.ok is False
    assert "embed" in result.detail.lower()


@pytest.mark.asyncio
async def test_verify_youtube_not_found():
    client = make_client(get_return=FakeResponse(404))
    result = await wv.verify_webcam("https://www.youtube.com/watch?v=abc123def", "youtube", client=client)
    assert result.ok is False


@pytest.mark.asyncio
async def test_verify_youtube_no_id_is_unsupported():
    client = make_client()
    result = await wv.verify_webcam("https://example.com/not-youtube", "youtube", client=client)
    assert result.ok is False
    assert result.status == "unsupported"
    client.get.assert_not_called()


@pytest.mark.asyncio
async def test_verify_webpage_reachable_but_never_embeddable():
    stream_resp = FakeStreamResponse(status_code=200)
    client = make_client(stream_return=stream_resp)
    result = await wv.verify_webcam("https://example.com/page", "webpage", client=client)
    assert result.ok is True
    assert "can't be shown" in result.detail


@pytest.mark.asyncio
async def test_verify_unknown_kind_unsupported():
    client = make_client()
    result = await wv.verify_webcam("https://example.com", "not-a-kind", client=client)
    assert result.ok is False
    assert result.status == "unsupported"


@pytest.mark.asyncio
async def test_verify_webcam_opens_and_closes_own_client_when_none_passed():
    with pytest.MonkeyPatch.context() as mp:
        fake_client = make_client(get_return=FakeResponse(200, {"content-type": "image/jpeg"}))
        fake_client.aclose = AsyncMock()
        mp.setattr(wv, "_new_client", lambda timeout: fake_client)
        result = await wv.verify_webcam("https://cam.example/snap.jpg", "snapshot")
    assert result.ok is True
    fake_client.aclose.assert_awaited_once()


def test_extract_youtube_id_shapes():
    assert wv.extract_youtube_id("https://www.youtube.com/watch?v=abc123def") == "abc123def"
    assert wv.extract_youtube_id("https://youtu.be/abc123def") == "abc123def"
    assert wv.extract_youtube_id("https://www.youtube.com/live/abc123def") == "abc123def"
    assert wv.extract_youtube_id("https://example.com/nope") is None
