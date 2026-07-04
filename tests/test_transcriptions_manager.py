"""Tests for TranscriptionsManager (pending/archive lifecycle)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.transcriptions.transcriptions_manager import TranscriptionsManager


def make_manager():
    tmpdir = tempfile.mkdtemp()
    return TranscriptionsManager(data_dir=tmpdir)


def test_add_and_get_pending():
    mgr = make_manager()
    mgr.add_transcription("user1", "first memo")
    mgr.add_transcription("user1", "second memo")

    pending = mgr.get_pending("user1")
    assert [t.content for t in pending] == ["first memo", "second memo"]
    assert all(t.source == "ios_app" for t in pending)


def test_pending_scoped_per_user():
    mgr = make_manager()
    mgr.add_transcription("user1", "belongs to user1")
    mgr.add_transcription("user2", "belongs to user2")

    assert [t.content for t in mgr.get_pending("user1")] == ["belongs to user1"]
    assert [t.content for t in mgr.get_pending("user2")] == ["belongs to user2"]


def test_archive_moves_from_pending_to_archived():
    mgr = make_manager()
    t1 = mgr.add_transcription("user1", "memo one")
    t2 = mgr.add_transcription("user1", "memo two")

    archived_count = mgr.archive("user1", [t1.id])

    assert archived_count == 1
    assert [t.id for t in mgr.get_pending("user1")] == [t2.id]
    assert [t.id for t in mgr.get_archived("user1")] == [t1.id]


def test_archive_unknown_id_is_noop():
    mgr = make_manager()
    mgr.add_transcription("user1", "memo")

    archived_count = mgr.archive("user1", ["does-not-exist"])

    assert archived_count == 0
    assert len(mgr.get_pending("user1")) == 1
    assert len(mgr.get_archived("user1")) == 0


def test_delete_transcription():
    mgr = make_manager()
    t1 = mgr.add_transcription("user1", "keep me")
    t2 = mgr.add_transcription("user1", "delete me")

    assert mgr.delete_transcription("user1", t2.id) is True
    assert [t.id for t in mgr.get_pending("user1")] == [t1.id]


def test_delete_unknown_transcription_returns_false():
    mgr = make_manager()
    assert mgr.delete_transcription("user1", "no-such-id") is False


def test_save_audio_remuxes_caf_into_playable_mp4():
    """iOS chunks are sometimes wrapped in a CAF container rather than real MP4 -
    browsers can't play CAF, so save_audio must remux (not just store raw bytes).

    Uses PCM audio for the synthetic fixture (this ffmpeg build can read but not
    write AAC-in-CAF - real iOS uploads are AAC-in-CAF, confirmed via ffprobe on
    an actual chunk); the remux itself is codec-agnostic container repackaging,
    so PCM-in-CAF exercises the same code path."""
    import subprocess

    mgr = make_manager()

    with tempfile.NamedTemporaryFile(suffix=".caf") as caf_file:
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", "-f", "caf", caf_file.name,
            ],
            check=True, timeout=30,
        )
        caf_bytes = Path(caf_file.name).read_bytes()

    filename = mgr.save_audio(caf_bytes)
    saved_path = mgr.audio_dir / filename

    assert saved_path.exists()
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", str(saved_path)],
        capture_output=True, text=True, timeout=30,
    )
    assert "format_name=mov,mp4,m4a,3gp,3g2,mj2" in probe.stdout
