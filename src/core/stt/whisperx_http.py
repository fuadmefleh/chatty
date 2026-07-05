"""WhisperX STT engine reachable over HTTP (run separately, not part of this
repo). Handles diarization itself (gracefully skipped server-side if it has
no HUGGINGFACE_TOKEN configured)."""
import httpx

from .base import STTProvider
from .types import TranscriptionResult


class WhisperXHTTPProvider(STTProvider):
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def transcribe(self, audio_bytes: bytes, filename_hint: str = "chunk.m4a") -> TranscriptionResult:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/transcribe",
                files={"file": (filename_hint, audio_bytes, "audio/mp4")},
                data={"language": "en", "diarize": "true"},
            )
            resp.raise_for_status()
            result = resp.json()

        return TranscriptionResult(
            text=(result.get("text") or "").strip(),
            segments=result.get("segments") or None,
            speaker_embeddings=result.get("speaker_embeddings") or None,
        )
