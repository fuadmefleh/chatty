import asyncio
import base64
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request

from src.core.stt import get_stt_provider
from src.web import config, media_processing, state
from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/media", tags=["media"], dependencies=[Depends(require_api_key)])


# ── Media ingestion (iOS app) ────────────────────────────────────────────────
# Raw-body (not multipart) single-file photo/video upload. Vision-describes
# images and summarizes videos (keyframes + audio track STT), then feeds the
# resulting text into the same TranscriptionsManager pending queue as audio/
# text transcriptions - the heartbeat's mining step picks it up unchanged.
# Never surfaced in Notes.
async def _process_image_media(
    media_bytes: bytes, image_format: str, device_id: str, caption: str,
    captured_at: str, source: str, filename: str,
) -> None:
    try:
        jpeg_b64 = await asyncio.to_thread(media_processing._convert_image_to_jpeg_b64, media_bytes, image_format)
    except Exception as e:
        state.logger.error(f"Failed to normalize image from device {device_id}: {e}")
        return

    prompt = (
        "Describe this photo in a few concise sentences: setting, people, "
        "objects, and anything notable. This description will be scanned "
        "for personal facts worth remembering, so include names, places, or "
        f"details mentioned in the caption if given.\n\nUser's caption: {caption or '(none)'}"
    )
    try:
        description = await media_processing._describe_image(jpeg_b64, prompt)
    except Exception as e:
        state.logger.error(f"Vision analysis failed for image from device {device_id}: {e}")
        return

    header = f"[{captured_at or datetime.utcnow().isoformat()}] (device {device_id}, image)"
    parts = [header, description.strip()]
    if caption:
        parts.append(f"Caption: {caption}")
    content = "\n".join(parts)

    state.transcriptions_manager.add_transcription(config.WEB_USER_ID, content, source=source, header=header)
    state.logger.info(f"Processed image media '{filename or '(unnamed)'}' from device {device_id}, queued for memory mining")


async def _process_video_media(
    media_bytes: bytes, video_format: str, device_id: str, caption: str,
    captured_at: str, source: str, filename: str,
) -> None:
    try:
        keyframes, audio_bytes = await asyncio.to_thread(media_processing._extract_video_parts, media_bytes, video_format)
    except Exception as e:
        state.logger.error(f"Failed to extract frames/audio from video from device {device_id}: {e}")
        return

    frame_descriptions = []
    for i, frame_bytes in enumerate(keyframes):
        frame_b64 = base64.b64encode(frame_bytes).decode("ascii")
        prompt = (
            f"This is frame {i + 1} of {len(keyframes)} sampled from a video, in "
            "chronological order. Describe what's happening in one or two sentences."
        )
        try:
            frame_descriptions.append((await media_processing._describe_image(frame_b64, prompt)).strip())
        except Exception as e:
            state.logger.error(f"Vision analysis failed for video frame {i} from device {device_id}: {e}")

    transcript = None
    if audio_bytes:
        try:
            result = await get_stt_provider().transcribe(audio_bytes, filename_hint="video_audio.m4a")
            transcript = (result.text or "").strip() or None
        except Exception as e:
            state.logger.error(f"STT failed for video audio from device {device_id}: {e}")

    if not frame_descriptions and not transcript:
        state.logger.info(f"Video from device {device_id} yielded no frame descriptions or transcript, skipping")
        return

    notes = "\n".join(f"Frame {i + 1}: {d}" for i, d in enumerate(frame_descriptions))
    if transcript:
        notes += f"\n\nAudio transcript: {transcript}"
    if caption:
        notes += f"\n\nUser's caption: {caption}"

    try:
        summary = (await media_processing._summarize_video_notes(notes)).strip()
    except Exception as e:
        state.logger.error(f"Failed to summarize video from device {device_id}: {e}")
        summary = notes  # fall back to the raw frame/transcript notes rather than dropping them

    header = f"[{captured_at or datetime.utcnow().isoformat()}] (device {device_id}, video)"
    content = f"{header} {summary}"

    state.transcriptions_manager.add_transcription(config.WEB_USER_ID, content, source=source, header=header)
    state.logger.info(f"Processed video media '{filename or '(unnamed)'}' from device {device_id}, queued for memory mining")


@router.post("", status_code=202)
async def receive_media(
    request: Request,
    background_tasks: BackgroundTasks,
    x_device_id: str = Header(default=""),
    x_media_kind: str = Header(default=""),
    x_source: str = Header(default="ios_app"),
    x_captured_at: str = Header(default=""),
    x_caption: str = Header(default=""),
    x_filename: str = Header(default=""),
):
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if content_type in config.MEDIA_IMAGE_FORMATS:
        kind, media_format = "image", config.MEDIA_IMAGE_FORMATS[content_type]
    elif content_type in config.MEDIA_VIDEO_FORMATS:
        kind, media_format = "video", config.MEDIA_VIDEO_FORMATS[content_type]
    else:
        raise HTTPException(status_code=415, detail=f"Unsupported content type: {content_type or '(none)'}")

    if x_media_kind and x_media_kind != kind:
        state.logger.warning(
            f"X-Media-Kind ({x_media_kind}) doesn't match Content-Type ({content_type}) "
            f"from device {x_device_id}; trusting Content-Type"
        )

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > config.MEDIA_MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"Media exceeds {config.MEDIA_MAX_BYTES:,} byte limit")

    media_bytes = await request.body()
    if not media_bytes:
        raise HTTPException(status_code=400, detail="Empty media body")
    if len(media_bytes) > config.MEDIA_MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"Media exceeds {config.MEDIA_MAX_BYTES:,} byte limit")

    caption = media_processing._decode_caption(x_caption)

    if kind == "image":
        background_tasks.add_task(
            _process_image_media, media_bytes, media_format, x_device_id, caption, x_captured_at, x_source, x_filename
        )
    else:
        background_tasks.add_task(
            _process_video_media, media_bytes, media_format, x_device_id, caption, x_captured_at, x_source, x_filename
        )
    return {"accepted": True}
