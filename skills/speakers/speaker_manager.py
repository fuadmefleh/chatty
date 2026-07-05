"""Speaker Manager - a named voice roster for labeling diarized transcript
segments, the audio analog of skills/facial_recognition's named-face roster.

Each roster entry accumulates multiple voice-embedding samples (not one
frozen vector) exactly like FaceRecognitionManager keeps every face encoding
for a person rather than averaging them - matching improves as more labeled
segments come in. Embeddings come from the external STT engine's diarization
step (see chatty_web_server.py's _transcribe_and_store_audio) and are plain
float lists, so storage is JSON only - no pickle needed.
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.core import config
from src.core.file_lock import locked

SPEAKER_MATCH_THRESHOLD = float(os.getenv("SPEAKER_MATCH_THRESHOLD", "0.75"))


class SpeakerManager:
    """Manages a per-user roster of named speakers with persistent JSON storage."""

    def __init__(self, data_dir: str = str(config.BASE_DIR / "data" / "speakers")):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_user_file(self, user_id: str) -> Path:
        return self.data_dir / f"{user_id}.json"

    def _load(self, path: Path) -> List[Dict]:
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading speakers from {path}: {e}")
            return []

    def _save(self, path: Path, speakers: List[Dict]) -> None:
        """Write atomically (temp file + rename) so a concurrent reader never
        observes a partially-written file even without holding the lock."""
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(speakers, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)

    def list_speakers(self, user_id: str) -> List[Dict]:
        """Return the roster with sample embeddings stripped (API-facing shape)."""
        speakers = self._load(self._get_user_file(user_id))
        return [self.to_public(s) for s in speakers]

    def get_speaker(self, user_id: str, speaker_id: str) -> Optional[Dict]:
        for s in self._load(self._get_user_file(user_id)):
            if s["id"] == speaker_id:
                return s
        return None

    def create_speaker(
        self, user_id: str, name: str, embedding: List[float],
        transcription_id: Optional[str] = None, start: Optional[float] = None,
        end: Optional[float] = None,
    ) -> Dict:
        path = self._get_user_file(user_id)
        with locked(path):
            speakers = self._load(path)
            now = datetime.now().isoformat()
            speaker = {
                "id": str(uuid.uuid4()),
                "name": name,
                "created_at": now,
                "updated_at": now,
                "samples": [self._make_sample(embedding, transcription_id, start, end)],
            }
            speakers.append(speaker)
            self._save(path, speakers)
            return speaker

    def add_sample(
        self, user_id: str, speaker_id: str, embedding: List[float],
        transcription_id: Optional[str] = None, start: Optional[float] = None,
        end: Optional[float] = None,
    ) -> Optional[Dict]:
        path = self._get_user_file(user_id)
        with locked(path):
            speakers = self._load(path)
            for s in speakers:
                if s["id"] == speaker_id:
                    s["samples"].append(self._make_sample(embedding, transcription_id, start, end))
                    s["updated_at"] = datetime.now().isoformat()
                    self._save(path, speakers)
                    return s
            return None

    def rename_speaker(self, user_id: str, speaker_id: str, name: str) -> Optional[Dict]:
        path = self._get_user_file(user_id)
        with locked(path):
            speakers = self._load(path)
            for s in speakers:
                if s["id"] == speaker_id:
                    s["name"] = name
                    s["updated_at"] = datetime.now().isoformat()
                    self._save(path, speakers)
                    return s
            return None

    def delete_speaker(self, user_id: str, speaker_id: str) -> bool:
        """Remove a speaker from the roster. Does NOT touch labels already
        written into transcripts - deleting only stops future matching."""
        path = self._get_user_file(user_id)
        with locked(path):
            speakers = self._load(path)
            remaining = [s for s in speakers if s["id"] != speaker_id]
            if len(remaining) == len(speakers):
                return False
            self._save(path, remaining)
            return True

    def match(self, user_id: str, embedding: List[float]) -> Optional[Tuple[Dict, float]]:
        """Find the best-matching known speaker for a voice embedding, comparing
        against every sample of every speaker (best global score wins).

        Returns (speaker, score) if the best score clears SPEAKER_MATCH_THRESHOLD,
        else None.
        """
        speakers = self._load(self._get_user_file(user_id))
        if not speakers:
            return None

        query = np.asarray(embedding, dtype=np.float64)
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return None
        query = query / query_norm

        best_speaker, best_score = None, -1.0
        for s in speakers:
            for sample in s["samples"]:
                vec = np.asarray(sample["embedding"], dtype=np.float64)
                norm = np.linalg.norm(vec)
                if norm == 0:
                    continue
                score = float(np.dot(query, vec / norm))
                if score > best_score:
                    best_speaker, best_score = s, score

        if best_speaker is not None and best_score >= SPEAKER_MATCH_THRESHOLD:
            return best_speaker, best_score
        return None

    @staticmethod
    def _make_sample(
        embedding: List[float], transcription_id: Optional[str],
        start: Optional[float], end: Optional[float],
    ) -> Dict:
        return {
            "embedding": embedding,
            "transcription_id": transcription_id,
            "start": start,
            "end": end,
            "added_at": datetime.now().isoformat(),
        }

    @staticmethod
    def to_public(speaker: Dict) -> Dict:
        """API-facing representation - no raw embeddings, just counts/sample refs."""
        samples = speaker.get("samples", [])
        last_sample = samples[-1] if samples else None
        return {
            "id": speaker["id"],
            "name": speaker["name"],
            "created_at": speaker["created_at"],
            "updated_at": speaker["updated_at"],
            "num_samples": len(samples),
            "sample_transcription_id": last_sample.get("transcription_id") if last_sample else None,
            "sample_start": last_sample.get("start") if last_sample else None,
            "sample_end": last_sample.get("end") if last_sample else None,
        }


# Singleton manager (speaker roster storage is already scoped by user_id per-call)
_manager: Optional[SpeakerManager] = None


def get_manager() -> SpeakerManager:
    global _manager
    if _manager is None:
        _manager = SpeakerManager()
    return _manager
