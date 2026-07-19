"""parakeet.cpp's OpenAI-compatible server (github.com/mudler/parakeet.cpp),
reachable over HTTP. No diarization or speaker embeddings - segments/
speaker_embeddings are left as None.

parakeet-server's example implementation only accepts WAV uploads, so
incoming chunks (m4a from the iOS app) are transcoded to 16kHz mono WAV with
ffmpeg before being POSTed.
"""
import asyncio
import subprocess
import tempfile

from openai import AsyncOpenAI

from .base import STTProvider
from .types import TranscriptionResult


class ParakeetHTTPProvider(STTProvider):
    def __init__(self, base_url: str, model: str = "parakeet"):
        self.client = AsyncOpenAI(base_url=base_url, api_key="not-needed")
        self.model = model

    async def transcribe(self, audio_bytes: bytes, filename_hint: str = "chunk.m4a") -> TranscriptionResult:
        wav_bytes = await asyncio.to_thread(_to_wav, audio_bytes, filename_hint)
        resp = await self.client.audio.transcriptions.create(
            model=self.model,
            file=("chunk.wav", wav_bytes, "audio/wav"),
        )
        return TranscriptionResult(text=(resp.text or "").strip())


def _to_wav(audio_bytes: bytes, filename_hint: str) -> bytes:
    suffix = "." + filename_hint.rsplit(".", 1)[-1] if "." in filename_hint else ".m4a"
    with tempfile.NamedTemporaryFile(suffix=suffix) as src, tempfile.NamedTemporaryFile(suffix=".wav") as dst:
        src.write(audio_bytes)
        src.flush()
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", src.name, "-ar", "16000", "-ac", "1", dst.name],
            check=True,
        )
        return dst.read()
