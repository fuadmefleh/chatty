"""STT provider interface."""
from abc import ABC, abstractmethod

from .types import TranscriptionResult


class STTProvider(ABC):
    """Transcribes raw audio bytes into text (+ optional diarization)."""

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, filename_hint: str = "chunk.m4a") -> TranscriptionResult:
        ...
