"""In-process open-source STT via faster-whisper. No diarization.

faster-whisper pulls in heavy binary deps (ctranslate2) and downloads model
weights on first use, so it's kept out of the base requirements.txt - see
requirements-local-stt.txt. The import is lazy (inside __init__) so picking
any other STT_PROVIDER never requires it to be installed.
"""
import asyncio
import tempfile

from .base import STTProvider
from .types import TranscriptionResult


class LocalWhisperProvider(STTProvider):
    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError(
                "STT_PROVIDER=local_whisper requires faster-whisper: "
                "pip install -r requirements-local-stt.txt"
            ) from e
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)

    async def transcribe(self, audio_bytes: bytes, filename_hint: str = "chunk.m4a") -> TranscriptionResult:
        def _run() -> str:
            suffix = "." + filename_hint.rsplit(".", 1)[-1] if "." in filename_hint else ".m4a"
            with tempfile.NamedTemporaryFile(suffix=suffix) as f:
                f.write(audio_bytes)
                f.flush()
                segments, _info = self._model.transcribe(f.name)
                return " ".join(seg.text.strip() for seg in segments).strip()

        text = await asyncio.to_thread(_run)
        return TranscriptionResult(text=text)
