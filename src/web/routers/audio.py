import re
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request

from skills.transcriptions.transcriptions_manager import render_segments
from src.core.stt import TranscriptionResult, get_stt_provider
from src.web import config, state
from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/audio", tags=["audio"], dependencies=[Depends(require_api_key)])


# ── Audio ingestion (iOS app) ────────────────────────────────────────────────
# Raw-body (not multipart) audio chunk upload. Transcribed via the WhisperX
# STT engine already running on this host, then fed into the same
# TranscriptionsManager pending queue as text transcriptions - the existing
# heartbeat mining step (HeartbeatManager._process_transcription_mining)
# picks it up from there unchanged.
def _normalize_segments(result: TranscriptionResult) -> Optional[List[dict]]:
    """Convert STT engine segments ({speaker, start, end, text}) into our
    stored shape ({local_speaker, start, end, text}). Returns None when the
    STT engine returned no segments at all, so callers can fall back to
    plain `text` instead of storing an empty segments list."""
    raw_segments = result.segments or []
    if not raw_segments:
        return None
    return [
        {
            "start": seg.get("start"),
            "end": seg.get("end"),
            "local_speaker": seg.get("speaker"),
            "text": (seg.get("text") or "").strip(),
        }
        for seg in raw_segments
    ]


# ── Assistant mode (wake-word push over the chat WebSocket) ─────────────────
_WAKE_WORD_RE = re.compile(r"\bchatty\b", re.IGNORECASE)
_ASSISTANT_FALLBACK_PROMPT = (
    "The user just said your name (\"Chatty\") in this audio chunk with nothing "
    "obvious following it. Check recent conversation context for what they might "
    "want; if nothing fits, just give a brief, natural acknowledgment like "
    "\"Yeah?\" or \"What's up?\" inviting them to continue."
)


def _extract_assistant_query(transcript: str) -> Optional[str]:
    """Return the text after the first "chatty" mention (trimmed), or None if
    "chatty" doesn't appear at all. An empty string (as opposed to None) means
    "chatty" was said with nothing following it - callers should treat that as
    a contentless wake word, not "no wake word", and fall back accordingly."""
    match = _WAKE_WORD_RE.search(transcript)
    if not match:
        return None
    return transcript[match.end():].strip()


async def _push_assistant_response(device_id: str, query: str) -> None:
    """Generate a response via the same agent/memory stack as the chat
    WebSocket and stream it over that device's open connection, if any. Silently
    drops the response (no error) when the device has no open connection, e.g.
    the app is backgrounded."""
    connection = state._active_chat_connections.get(device_id)
    if connection is None:
        state.logger.info(f"No open chat WebSocket for device {device_id}; dropping assistant push")
        return

    from src.agents.web_chat_agent import WebChatAgent
    from src.core.memory import MemoryManager

    memory_manager = MemoryManager(config.WEB_USER_ID)
    agent = WebChatAgent(skills_manager=state.skills_manager, memory_manager=memory_manager)

    try:
        async for chunk in agent.stream(query):
            await connection.send_json({"type": "chunk", "content": chunk})
        await connection.send_json({"type": "done"})
    except Exception as e:
        state.logger.error(f"Failed to push assistant response to device {device_id}: {e}")


async def _transcribe_and_store_audio(
    audio_bytes: bytes, device_id: str, chunk_start: str, chunk_duration: str, source: str,
    assistant_mode: bool = False,
) -> None:
    try:
        result = await get_stt_provider().transcribe(audio_bytes, filename_hint="chunk.m4a")

        segments = _normalize_segments(result)
        speaker_embeddings = result.speaker_embeddings or {}

        # Auto-label any local speaker whose voice already matches a known
        # roster entry - the "face recognition recognizes you automatically"
        # step for brand-new recordings.
        speaker_labels = {}
        for local_speaker, embedding in speaker_embeddings.items():
            match = state.speaker_manager.match(config.WEB_USER_ID, embedding)
            if match:
                speaker_labels[local_speaker] = match[0]["name"]

        transcript = render_segments(segments, speaker_labels) if segments else result.text
        if not transcript:
            state.logger.info(f"Audio chunk from device {device_id} at {chunk_start} had no speech, skipping")
            return

        if assistant_mode:
            query = _extract_assistant_query(transcript)
            if query is not None:
                # Wake word detected: handle as a proactive assistant query
                # instead of a regular transcript segment, so it's never also
                # mined into long-term memory (the exchange itself still lands
                # in memory via WebChatAgent.stream's own add_interaction call).
                state.logger.info(f"Assistant wake word detected from device {device_id} at {chunk_start}")
                await _push_assistant_response(device_id, query or _ASSISTANT_FALLBACK_PROMPT)
                return

        audio_filename = state.transcriptions_manager.save_audio(audio_bytes)
        header = f"[{chunk_start}] (device {device_id}, {chunk_duration}s audio)"
        content = f"{header} {transcript}"
        state.transcriptions_manager.add_transcription(
            config.WEB_USER_ID, content, source=source, audio_filename=audio_filename,
            segments=segments, speaker_embeddings=speaker_embeddings or None,
            speaker_labels=speaker_labels or None, header=header,
        )
        state.logger.info(f"Transcribed and queued audio chunk from device {device_id} at {chunk_start}")

    except Exception as e:
        state.logger.error(f"Failed to transcribe audio chunk from device {device_id} at {chunk_start}: {e}")


@router.post("", status_code=202)
async def receive_audio(
    request: Request,
    background_tasks: BackgroundTasks,
    x_device_id: str = Header(default=""),
    x_chunk_start: str = Header(default=""),
    x_chunk_duration: str = Header(default=""),
    x_source: str = Header(default="ios_app"),
    x_mode: str = Header(default=""),
):
    audio_bytes = await request.body()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio body")

    background_tasks.add_task(
        _transcribe_and_store_audio, audio_bytes, x_device_id, x_chunk_start, x_chunk_duration, x_source,
        x_mode.strip().lower() == "assistant",
    )
    return {"accepted": True}
