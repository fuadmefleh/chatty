"""Transcriptions Manager - handles raw transcriptions (e.g. iOS voice memos)
awaiting automatic memory mining.

Distinct from skills/notes/notes_manager.py: notes are user-authored and
user-managed indefinitely, while transcriptions are a staging area that
HeartbeatManager drains every cycle by extracting long-term-memory-worthy
content (see MemoryManager.consolidate_text) and archiving the raw text.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import uuid


class Transcription:
    """Represents a single raw transcription pending (or already) mined into memory."""

    def __init__(
        self, transcription_id: str, content: str, created_at: str, user_id: str,
        source: str = "ios_app", audio_filename: Optional[str] = None,
    ):
        self.id = transcription_id
        self.content = content
        self.created_at = created_at
        self.user_id = user_id
        self.source = source
        self.audio_filename = audio_filename

    def to_dict(self) -> Dict:
        """API-facing representation - exposes has_audio, not the on-disk filename."""
        return {
            "id": self.id,
            "content": self.content,
            "created_at": self.created_at,
            "user_id": self.user_id,
            "source": self.source,
            "has_audio": self.audio_filename is not None,
        }

    def to_storage_dict(self) -> Dict:
        """On-disk representation - includes the audio filename so it survives reloads."""
        d = self.to_dict()
        d["audio_filename"] = self.audio_filename
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> 'Transcription':
        return cls(
            transcription_id=data["id"],
            content=data["content"],
            created_at=data["created_at"],
            user_id=data["user_id"],
            source=data.get("source", "ios_app"),
            audio_filename=data.get("audio_filename"),
        )


class TranscriptionsManager:
    """Manages pending/archived transcriptions with persistent JSON storage.

    Pending transcriptions live in data/transcriptions/<user_id>.json.
    Once mined into long-term memory, they're moved into
    data/transcriptions/archived/<user_id>.json - keeping the raw text
    available without cluttering the pending list.
    """

    def __init__(self, data_dir: str = "/home/edgeworks-server/chatty/data/transcriptions"):
        self.data_dir = Path(data_dir)
        self.archived_dir = self.data_dir / "archived"
        self.audio_dir = self.data_dir / "audio"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.archived_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def _get_user_file(self, user_id: str) -> Path:
        return self.data_dir / f"{user_id}.json"

    def _get_archived_file(self, user_id: str) -> Path:
        return self.archived_dir / f"{user_id}.json"

    def _load(self, path: Path) -> List[Transcription]:
        if not path.exists():
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [Transcription.from_dict(item) for item in data]
        except Exception as e:
            print(f"Error loading transcriptions from {path}: {e}")
            return []

    def _save(self, path: Path, transcriptions: List[Transcription]) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump([t.to_storage_dict() for t in transcriptions], f, indent=2, ensure_ascii=False)

    def save_audio(self, audio_bytes: bytes, ext: str = "m4a") -> str:
        """Write an audio chunk to disk (remuxed into a real MP4 container so
        it's browser-playable) and return its filename (not full path).

        The iOS app's chunks are AAC audio but sometimes actually arrive
        wrapped in a CAF (Core Audio Format) container despite the .m4a/
        audio-mp4 labeling - ffmpeg-based tools (WhisperX, ffprobe) read
        either happily, which is why transcription works regardless, but
        browsers' native <audio> element can't play CAF. Remux (not
        re-encode - fast, lossless) via ffmpeg so playback works no matter
        which container the upload actually used.
        """
        import subprocess
        import tempfile

        filename = f"{uuid.uuid4()}.{ext}"
        dest_path = self.audio_dir / filename

        with tempfile.NamedTemporaryFile(suffix=".input") as tmp_in:
            tmp_in.write(audio_bytes)
            tmp_in.flush()
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-i", tmp_in.name, "-c", "copy", "-f", "mp4", str(dest_path)],
                    check=True, timeout=30,
                )
            except Exception as e:
                print(f"Error remuxing audio to mp4, saving raw bytes instead: {e}")
                with open(dest_path, 'wb') as f:
                    f.write(audio_bytes)

        return filename

    def get_audio_path(self, user_id: str, transcription_id: str) -> Optional[Path]:
        """Resolve the on-disk audio file for a transcription, pending or archived."""
        for t in self._load(self._get_user_file(user_id)) + self._load(self._get_archived_file(user_id)):
            if t.id == transcription_id:
                return self.audio_dir / t.audio_filename if t.audio_filename else None
        return None

    def add_transcription(
        self, user_id: str, content: str, source: str = "ios_app", audio_filename: Optional[str] = None,
    ) -> Transcription:
        """Add a new pending transcription for a user."""
        pending = self._load(self._get_user_file(user_id))

        new_transcription = Transcription(
            transcription_id=str(uuid.uuid4()),
            content=content,
            created_at=datetime.now().isoformat(),
            user_id=user_id,
            source=source,
            audio_filename=audio_filename,
        )

        pending.append(new_transcription)
        self._save(self._get_user_file(user_id), pending)

        return new_transcription

    def get_pending(self, user_id: str) -> List[Transcription]:
        """Get all not-yet-mined transcriptions for a user, oldest first."""
        pending = self._load(self._get_user_file(user_id))
        return sorted(pending, key=lambda t: t.created_at)

    def get_archived(self, user_id: str) -> List[Transcription]:
        """Get all already-mined transcriptions for a user, newest first."""
        archived = self._load(self._get_archived_file(user_id))
        return sorted(archived, key=lambda t: t.created_at, reverse=True)

    def delete_transcription(self, user_id: str, transcription_id: str) -> bool:
        """Delete a specific pending transcription (does not touch the archive)."""
        pending = self._load(self._get_user_file(user_id))
        to_delete = [t for t in pending if t.id == transcription_id]
        if not to_delete:
            return False

        pending = [t for t in pending if t.id != transcription_id]
        self._save(self._get_user_file(user_id), pending)

        for t in to_delete:
            if t.audio_filename:
                (self.audio_dir / t.audio_filename).unlink(missing_ok=True)
        return True

    def archive(self, user_id: str, transcription_ids: List[str]) -> int:
        """Move the given pending transcriptions into the archive.

        Returns the number of transcriptions actually archived.
        """
        pending = self._load(self._get_user_file(user_id))
        to_archive = [t for t in pending if t.id in transcription_ids]
        if not to_archive:
            return 0

        remaining = [t for t in pending if t.id not in transcription_ids]
        archived = self._load(self._get_archived_file(user_id))
        archived.extend(to_archive)

        self._save(self._get_user_file(user_id), remaining)
        self._save(self._get_archived_file(user_id), archived)
        return len(to_archive)
