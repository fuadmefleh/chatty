"""Normalized types for STT providers."""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class TranscriptionResult:
    """Result of transcribing one audio chunk.

    segments/speaker_embeddings stay in WhisperX's own shape
    ({start,end,speaker,text} / {label: embedding}) since that's the one
    existing consumer (chatty_web_server._normalize_segments) already
    expects. Non-diarizing providers just leave them as None.
    """
    text: str
    segments: Optional[List[Dict]] = None
    speaker_embeddings: Optional[Dict[str, list]] = None
