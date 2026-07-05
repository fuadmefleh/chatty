"""OpenAI transcription API (whisper-1 / gpt-4o-transcribe). No diarization
or speaker embeddings — segments/speaker_embeddings are left as None."""
from openai import AsyncOpenAI

from .base import STTProvider
from .types import TranscriptionResult


class OpenAITranscriptionProvider(STTProvider):
    def __init__(self, api_key: str, model: str = "whisper-1"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def transcribe(self, audio_bytes: bytes, filename_hint: str = "chunk.m4a") -> TranscriptionResult:
        resp = await self.client.audio.transcriptions.create(
            model=self.model,
            file=(filename_hint, audio_bytes, "audio/mp4"),
        )
        return TranscriptionResult(text=(resp.text or "").strip())
