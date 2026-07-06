"""Tests for interactive chat media:
- POST /api/chatty/chat/attachments (upload) and GET /api/chatty/chat-media/{filename} (serve)
- _build_attachment_context / _load_chat_attachment_context (vision/STT description for a
  live chat turn - see websocket_chat's attachment_id handling)
- ConversationHistoryManager carrying attachment metadata through append()/get_session()
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import chatty_web_server as server
from src.core.memory import ConversationHistoryManager


@pytest.fixture
def client():
    # Plain TestClient (not used as a context manager) does NOT run the
    # @app.on_event("startup") handler, so this never touches SkillsManager.
    return TestClient(server.app)


@pytest.fixture(autouse=True)
def isolated_uploads(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(server, "WEB_USER_ID", "web_user")
    yield


def _auth_headers(**overrides):
    headers = {"X-API-Key": server.API_KEY}
    headers.update(overrides)
    return headers


def _seed_file(name: str, data: bytes = b"hello") -> str:
    path = server._chat_uploads_dir() / name
    path.write_bytes(data)
    return name


# ── POST /api/chatty/chat/attachments ───────────────────────────────────────

def test_upload_wrong_api_key_rejected(client):
    resp = client.post(
        "/api/chatty/chat/attachments",
        files={"file": ("photo.jpg", b"fake-bytes", "image/jpeg")},
        headers=_auth_headers(**{"X-API-Key": "wrong"}),
    )
    assert resp.status_code == 401


def test_upload_unsupported_content_type_rejected(client):
    resp = client.post(
        "/api/chatty/chat/attachments",
        files={"file": ("doc.pdf", b"fake-bytes", "application/pdf")},
        headers=_auth_headers(),
    )
    assert resp.status_code == 415


def test_upload_empty_file_rejected(client):
    resp = client.post(
        "/api/chatty/chat/attachments",
        files={"file": ("photo.jpg", b"", "image/jpeg")},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400


def test_upload_oversize_file_rejected(client, monkeypatch):
    monkeypatch.setattr(server, "CHAT_ATTACHMENT_MAX_BYTES", 10)
    resp = client.post(
        "/api/chatty/chat/attachments",
        files={"file": ("photo.jpg", b"x" * 20, "image/jpeg")},
        headers=_auth_headers(),
    )
    assert resp.status_code == 413


def test_upload_image_success_writes_file_and_returns_metadata(client):
    resp = client.post(
        "/api/chatty/chat/attachments",
        files={"file": ("photo.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "image"
    assert body["id"].endswith(".jpg")
    assert body["url"] == f"/api/chatty/chat-media/{body['id']}"

    stored = server._chat_uploads_dir() / body["id"]
    assert stored.read_bytes() == b"fake-jpeg-bytes"


def test_upload_video_success(client):
    resp = client.post(
        "/api/chatty/chat/attachments",
        files={"file": ("clip.mp4", b"fake-mp4-bytes", "video/mp4")},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201
    assert resp.json()["kind"] == "video"


# ── GET /api/chatty/chat-media/{filename} ───────────────────────────────────

def test_get_chat_media_requires_auth(client):
    name = _seed_file("11111111-1111-1111-1111-111111111111.png")
    resp = client.get(f"/api/chatty/chat-media/{name}")
    assert resp.status_code == 401


def test_get_chat_media_accepts_header_auth(client):
    name = _seed_file("11111111-1111-1111-1111-111111111112.png", b"pngdata")
    resp = client.get(f"/api/chatty/chat-media/{name}", headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.content == b"pngdata"
    assert resp.headers["content-type"] == "image/png"


def test_get_chat_media_accepts_query_param_auth(client):
    name = _seed_file("11111111-1111-1111-1111-111111111113.mp4", b"videodata")
    resp = client.get(f"/api/chatty/chat-media/{name}?api_key={server.API_KEY}")
    assert resp.status_code == 200
    assert resp.content == b"videodata"
    assert resp.headers["content-type"] == "video/mp4"


def test_get_chat_media_wrong_query_key_rejected(client):
    name = _seed_file("11111111-1111-1111-1111-111111111114.png")
    resp = client.get(f"/api/chatty/chat-media/{name}?api_key=wrong")
    assert resp.status_code == 401


def test_get_chat_media_rejects_invalid_filename(client):
    resp = client.get("/api/chatty/chat-media/not-a-uuid.png", headers=_auth_headers())
    assert resp.status_code == 400


def test_get_chat_media_rejects_traversal_style_filename(client):
    # Never resolves to file content outside the uploads dir, whatever status it returns.
    resp = client.get("/api/chatty/chat-media/%2e%2e%2fsecrets.png", headers=_auth_headers())
    assert resp.status_code != 200


def test_get_chat_media_missing_file_404s(client):
    resp = client.get(
        "/api/chatty/chat-media/11111111-1111-1111-1111-111111111115.png",
        headers=_auth_headers(),
    )
    assert resp.status_code == 404


# ── _build_attachment_context ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_attachment_context_image(monkeypatch):
    monkeypatch.setattr(server, "_convert_image_to_jpeg_b64", lambda data, ext: "b64data")
    describe_mock = AsyncMock(return_value="A photo of a cat on a windowsill.")
    monkeypatch.setattr(server, "_describe_image", describe_mock)

    result = await server._build_attachment_context(b"fake-bytes", "jpg", "image", "look at my cat")

    assert result == "A photo of a cat on a windowsill."
    describe_mock.assert_awaited_once()
    assert describe_mock.await_args.args[0] == "b64data"
    assert "look at my cat" in describe_mock.await_args.args[1]


@pytest.mark.asyncio
async def test_build_attachment_context_video_combines_frames_and_transcript(monkeypatch):
    monkeypatch.setattr(
        server, "_extract_video_parts", lambda data, ext: ([b"frame1", b"frame2"], b"audio-bytes")
    )
    describe_mock = AsyncMock(side_effect=["A person waving.", "A dog running."])
    monkeypatch.setattr(server, "_describe_image", describe_mock)

    fake_stt = MagicMock()
    fake_stt.transcribe = AsyncMock(return_value=MagicMock(text="hello from the video"))
    monkeypatch.setattr(server, "get_stt_provider", lambda: fake_stt)

    result = await server._build_attachment_context(b"fake-video-bytes", "mp4", "video", "check this out")

    assert "Frame 1: A person waving." in result
    assert "Frame 2: A dog running." in result
    assert "Audio transcript: hello from the video" in result
    assert "User's message: check this out" in result


@pytest.mark.asyncio
async def test_build_attachment_context_video_no_frames_or_audio(monkeypatch):
    monkeypatch.setattr(server, "_extract_video_parts", lambda data, ext: ([], None))
    monkeypatch.setattr(server, "get_stt_provider", lambda: MagicMock())

    result = await server._build_attachment_context(b"bytes", "mp4", "video", None)
    assert "couldn't be analyzed" in result


# ── _load_chat_attachment_context ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_load_chat_attachment_context_invalid_id():
    context, meta = await server._load_chat_attachment_context("../../etc/passwd", None)
    assert meta is None
    assert "invalid" in context.lower()


@pytest.mark.asyncio
async def test_load_chat_attachment_context_missing_file():
    context, meta = await server._load_chat_attachment_context(
        "22222222-2222-2222-2222-222222222222.jpg", None
    )
    assert meta is None
    assert "could not be found" in context.lower()


@pytest.mark.asyncio
async def test_load_chat_attachment_context_success(monkeypatch):
    name = _seed_file("33333333-3333-3333-3333-333333333333.jpg", b"jpegbytes")
    describe_mock = AsyncMock(return_value="A sunset over the mountains.")
    monkeypatch.setattr(server, "_build_attachment_context", describe_mock)

    context, meta = await server._load_chat_attachment_context(name, "look at this")

    assert meta == {"kind": "image", "url": f"/api/chatty/chat-media/{name}"}
    assert "sunset over the mountains" in context
    describe_mock.assert_awaited_once_with(b"jpegbytes", "jpg", "image", "look at this")


# ── ConversationHistoryManager attachment metadata ──────────────────────────

def _make_history_mgr(tmp_path):
    mgr = ConversationHistoryManager.__new__(ConversationHistoryManager)
    mgr.user_id = "test_user"
    history_dir = tmp_path / "conversations"
    history_dir.mkdir(parents=True, exist_ok=True)
    mgr._path = history_dir / "history.json"
    return mgr


@pytest.mark.asyncio
async def test_history_append_and_get_session_carry_attachment(tmp_path):
    mgr = _make_history_mgr(tmp_path)
    await mgr.append(
        "check this out", "Nice photo!",
        attachment={"kind": "image", "url": "/api/chatty/chat-media/x.jpg"},
    )

    session_msgs = await mgr.get_session(0)
    assert session_msgs[0] == {
        "role": "user",
        "content": "check this out",
        "attachment": {"kind": "image", "url": "/api/chatty/chat-media/x.jpg"},
    }
    assert session_msgs[1] == {"role": "assistant", "content": "Nice photo!"}


@pytest.mark.asyncio
async def test_history_append_without_attachment_omits_key(tmp_path):
    mgr = _make_history_mgr(tmp_path)
    await mgr.append("hello", "hi there")

    session_msgs = await mgr.get_session(0)
    assert "attachment" not in session_msgs[0]
