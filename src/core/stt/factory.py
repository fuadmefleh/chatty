"""Factory for selecting the configured STT backend."""
from typing import Optional

from src.core import config

from .base import STTProvider
from .whisperx_http import WhisperXHTTPProvider

_stt_singleton: Optional[STTProvider] = None


def get_stt_provider() -> STTProvider:
    global _stt_singleton
    if _stt_singleton is None:
        if config.STT_PROVIDER == "openai":
            from .openai_provider import OpenAITranscriptionProvider
            _stt_singleton = OpenAITranscriptionProvider(
                api_key=config.OPENAI_API_KEY, model=config.STT_OPENAI_MODEL
            )
        elif config.STT_PROVIDER == "local_whisper":
            from .local_whisper import LocalWhisperProvider
            _stt_singleton = LocalWhisperProvider(
                model_size=config.STT_LOCAL_MODEL_SIZE, device=config.STT_LOCAL_DEVICE
            )
        elif config.STT_PROVIDER == "parakeet":
            from .parakeet_http import ParakeetHTTPProvider
            _stt_singleton = ParakeetHTTPProvider(
                base_url=config.STT_PARAKEET_URL, model=config.STT_PARAKEET_MODEL
            )
        else:
            _stt_singleton = WhisperXHTTPProvider(base_url=config.STT_ENGINE_URL)
    return _stt_singleton
