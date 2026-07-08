"""Vision/STT pipeline shared by passive media ingestion (routers/media.py)
and interactive chat attachments (routers/chat_media.py). Consolidates what
used to be two near-duplicate implementations of the same
convert-image/extract-video-parts/describe/transcribe steps."""
import asyncio
import base64
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from src.core.stt import get_stt_provider
from src.web import config


def _chat_uploads_dir() -> Path:
    d = config.MEMORY_DIR / config.WEB_USER_ID / "uploads" / "chat"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _decode_caption(raw: str) -> Optional[str]:
    from urllib.parse import unquote

    if not raw:
        return None
    try:
        decoded = unquote(raw, encoding="utf-8", errors="strict")
    except Exception:
        decoded = raw
    return decoded.strip() or None


async def _describe_image(jpeg_b64: str, prompt: str) -> str:
    """Vision-describe a single JPEG image, falling back to a one-off OpenAI
    vision call if the configured chat provider doesn't support vision -
    same fallback src.main's Telegram photo handler uses."""
    from src.core import config as core_config
    from src.core.llm.factory import get_llm_provider
    from src.core.llm.openai_provider import OpenAIProvider

    provider = get_llm_provider()
    if provider.supports_vision:
        return await provider.complete_vision(prompt, image_b64=jpeg_b64, max_tokens=500)
    if core_config.OPENAI_API_KEY:
        fallback = OpenAIProvider(
            api_key=core_config.OPENAI_API_KEY, base_url=None, model="gpt-4o", supports_vision=True,
        )
        return await fallback.complete_vision(prompt, image_b64=jpeg_b64, max_tokens=500)
    raise RuntimeError("No vision-capable LLM provider configured (set OPENAI_API_KEY, or CHAT_PROVIDER=anthropic)")


async def _summarize_video_notes(raw_notes: str) -> str:
    from src.core.llm.factory import get_llm_provider

    prompt = (
        "Summarize this video into a short paragraph, combining what happens "
        "visually across the sampled frames with anything said in the audio "
        "transcript (if present). Focus on facts worth remembering: people, "
        "places, events, plans.\n\n" + raw_notes
    )
    response = await get_llm_provider().complete([{"role": "user", "content": prompt}])
    return response.content


def _convert_image_to_jpeg_b64(image_bytes: bytes, image_format: str) -> str:
    """Normalize any supported image format (jpeg/heic/png) to real JPEG
    bytes via ImageMagick (auto-orienting per EXIF), since the vision
    providers' complete_vision() hardcodes an image/jpeg mime type in the
    request payload - HEIC in particular isn't understood by either vision
    API directly."""
    result = subprocess.run(
        ["convert", f"{image_format}:-", "-auto-orient", "jpeg:-"],
        input=image_bytes, capture_output=True, timeout=30, check=True,
    )
    return base64.b64encode(result.stdout).decode("ascii")


def _ffprobe_duration(path: str) -> Optional[float]:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=15, check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def _extract_frame_at(path: str, timestamp: float) -> Optional[bytes]:
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", str(timestamp), "-i", path,
             "-frames:v", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
            capture_output=True, timeout=30, check=True,
        )
        return result.stdout or None
    except Exception:
        return None


def _extract_audio_track(path: str) -> Optional[bytes]:
    """Extract the audio track as an mp4/m4a file. Written to a real temp
    file rather than piped to stdout - the mp4 muxer needs a seekable
    output to write its header, unlike the mjpeg frame grabs above."""
    with tempfile.NamedTemporaryFile(suffix=".m4a") as tmp_out:
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", path, "-vn", "-acodec", "aac", "-f", "mp4", tmp_out.name],
                capture_output=True, timeout=60, check=True,
            )
        except Exception:
            return None
        data = tmp_out.read()
        return data or None


def _extract_video_parts(video_bytes: bytes, video_format: str) -> Tuple[List[bytes], Optional[bytes]]:
    with tempfile.NamedTemporaryFile(suffix=f".{video_format}") as tmp_in:
        tmp_in.write(video_bytes)
        tmp_in.flush()

        duration = _ffprobe_duration(tmp_in.name)
        fractions = [0.1, 0.5, 0.9] if duration else [0.0]
        keyframes = []
        for frac in fractions[:config.MEDIA_VIDEO_KEYFRAME_COUNT]:
            timestamp = duration * frac if duration else 0.0
            frame = _extract_frame_at(tmp_in.name, timestamp)
            if frame:
                keyframes.append(frame)

        audio_bytes = _extract_audio_track(tmp_in.name)

    return keyframes, audio_bytes


async def _build_attachment_context(media_bytes: bytes, ext: str, kind: str, caption: Optional[str]) -> str:
    """Describe an image/video attached to a live chat message, for use as
    ephemeral LLM context (WebChatAgent.stream's attachment_context). Reuses
    the same vision/STT helpers as the passive media-ingestion pipeline, but
    skips that pipeline's final video-summarization pass (needed there for
    memory-log framing) since here the chat model synthesizes its own reply
    from the raw per-frame notes."""
    if kind == "image":
        jpeg_b64 = await asyncio.to_thread(_convert_image_to_jpeg_b64, media_bytes, ext)
        prompt = (
            "Describe this image in detail so you (an AI assistant) can discuss it with the "
            "user: setting, people, objects, text, and anything notable."
        )
        if caption:
            prompt += f"\n\nThe user's message accompanying it: {caption}"
        return await _describe_image(jpeg_b64, prompt)

    keyframes, audio_bytes = await asyncio.to_thread(_extract_video_parts, media_bytes, ext)
    frame_descriptions = []
    for i, frame_bytes in enumerate(keyframes):
        frame_b64 = base64.b64encode(frame_bytes).decode("ascii")
        prompt = (
            f"This is frame {i + 1} of {len(keyframes)} sampled from a video the user just "
            "attached to a chat message, in chronological order. Describe what's happening "
            "in one or two sentences."
        )
        try:
            frame_descriptions.append((await _describe_image(frame_b64, prompt)).strip())
        except Exception as e:
            from src.web import state
            state.logger.error(f"Vision analysis failed for chat video frame {i}: {e}")

    transcript = None
    if audio_bytes:
        try:
            result = await get_stt_provider().transcribe(audio_bytes, filename_hint="video_audio.m4a")
            transcript = (result.text or "").strip() or None
        except Exception as e:
            from src.web import state
            state.logger.error(f"STT failed for chat video audio: {e}")

    if not frame_descriptions and not transcript:
        return "(The video couldn't be analyzed - no usable frames or audio.)"

    parts = [f"Frame {i + 1}: {d}" for i, d in enumerate(frame_descriptions)]
    if transcript:
        parts.append(f"Audio transcript: {transcript}")
    if caption:
        parts.append(f"User's message: {caption}")
    return "\n".join(parts)


async def _load_chat_attachment_context(
    attachment_id: str, caption: Optional[str],
) -> Tuple[Optional[str], Optional[dict]]:
    """Load a previously-uploaded chat attachment (see routers.chat_media.
    upload_chat_attachment) and describe it. Returns
    (attachment_context_for_the_llm, metadata_for_history)."""
    from src.web import state

    if not config.CHAT_MEDIA_FILENAME_RE.match(attachment_id):
        return "(The attachment reference was invalid.)", None

    path = _chat_uploads_dir() / attachment_id
    if not path.is_file():
        return "(The attachment could not be found - it may have expired.)", None

    ext = attachment_id.rsplit(".", 1)[-1]
    kind = "video" if ext in config.CHAT_MEDIA_VIDEO_EXTS else "image"
    meta = {"kind": kind, "url": f"/api/chatty/chat-media/{attachment_id}"}

    try:
        media_bytes = await asyncio.to_thread(path.read_bytes)
        description = await _build_attachment_context(media_bytes, ext, kind, caption)
    except Exception as e:
        state.logger.error(f"Failed to analyze chat attachment {attachment_id}: {e}")
        description = f"(The user attached a {kind}, but it couldn't be analyzed.)"

    # Grafted onto the user's own message by WebChatAgent._build_messages
    # (attachment_context), not sent as a separate system note - live-tested
    # against this deployment's local model and found that a system-level
    # "here's what the image shows, don't say you can't see images" note
    # reliably got overridden by the model's trained "I can't view images"
    # refusal once real memory context padded the conversation. Folding the
    # description into what the user is literally saying doesn't trigger that.
    return f"[Attached {kind} - here's what it shows: {description}]", meta
