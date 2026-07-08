"""Tests for TranscriptionsManager (pending/archive lifecycle)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.transcriptions.transcriptions_manager import TranscriptionsManager, render_segments


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


def test_render_segments_resolves_labels_and_falls_back_to_local_speaker():
    segments = [
        {"start": 0.0, "end": 1.0, "local_speaker": "SPEAKER_00", "text": "hi"},
        {"start": 1.0, "end": 2.0, "local_speaker": "SPEAKER_01", "text": "hello"},
    ]
    assert render_segments(segments) == "SPEAKER_00: hi\nSPEAKER_01: hello"
    assert render_segments(segments, {"SPEAKER_00": "Fuad"}) == "Fuad: hi\nSPEAKER_01: hello"


def test_render_segments_skips_empty_text_and_bare_lines_without_speaker():
    segments = [
        {"start": 0.0, "end": 1.0, "local_speaker": None, "text": "no speaker info"},
        {"start": 1.0, "end": 2.0, "local_speaker": "SPEAKER_00", "text": ""},
    ]
    assert render_segments(segments) == "no speaker info"


def test_add_transcription_with_segments_exposes_has_segments():
    mgr = make_manager()
    segments = [{"start": 0.0, "end": 1.0, "local_speaker": "SPEAKER_00", "text": "hi"}]
    t = mgr.add_transcription(
        "user1", "SPEAKER_00: hi", segments=segments,
        speaker_embeddings={"SPEAKER_00": [0.1, 0.2]},
    )
    assert t.to_dict()["has_segments"] is True

    plain = mgr.add_transcription("user1", "no segments here")
    assert plain.to_dict()["has_segments"] is False


def test_update_transcription_regenerates_content_from_labels():
    mgr = make_manager()
    segments = [
        {"start": 0.0, "end": 1.0, "local_speaker": "SPEAKER_00", "text": "hi"},
        {"start": 1.0, "end": 2.0, "local_speaker": "SPEAKER_01", "text": "hello"},
    ]
    t = mgr.add_transcription("user1", render_segments(segments), segments=segments)

    updated = mgr.update_transcription("user1", t.id, speaker_labels={"SPEAKER_00": "Fuad"})

    assert updated.content == "Fuad: hi\nSPEAKER_01: hello"
    assert mgr.get_pending("user1")[0].content == "Fuad: hi\nSPEAKER_01: hello"


def test_update_transcription_preserves_header_prefix():
    mgr = make_manager()
    segments = [{"start": 0.0, "end": 1.0, "local_speaker": "SPEAKER_00", "text": "hi"}]
    header = "[2026-01-01T00:00:00.000Z] (device abc, 5.0s audio)"
    t = mgr.add_transcription(
        "user1", f"{header} SPEAKER_00: hi", segments=segments, header=header,
    )

    updated = mgr.update_transcription("user1", t.id, speaker_labels={"SPEAKER_00": "Fuad"})

    assert updated.content == f"{header} Fuad: hi"


def test_update_transcription_finds_archived_records_too():
    mgr = make_manager()
    segments = [{"start": 0.0, "end": 1.0, "local_speaker": "SPEAKER_00", "text": "hi"}]
    t = mgr.add_transcription("user1", render_segments(segments), segments=segments)
    mgr.archive("user1", [t.id])

    updated = mgr.update_transcription("user1", t.id, speaker_labels={"SPEAKER_00": "Fuad"})

    assert updated is not None
    assert mgr.get_archived("user1")[0].content == "Fuad: hi"


def test_update_transcription_unknown_id_returns_none():
    mgr = make_manager()
    assert mgr.update_transcription("user1", "no-such-id", speaker_labels={}) is None


def test_update_transcriptions_batch_touches_multiple_records_across_both_files():
    mgr = make_manager()
    segments = [{"start": 0.0, "end": 1.0, "local_speaker": "SPEAKER_00", "text": "hi"}]
    pending_t = mgr.add_transcription("user1", render_segments(segments), segments=segments)
    archived_t = mgr.add_transcription("user1", render_segments(segments), segments=segments)
    mgr.archive("user1", [archived_t.id])

    touched = mgr.update_transcriptions_batch("user1", {
        pending_t.id: {"speaker_labels": {"SPEAKER_00": "Fuad"}},
        archived_t.id: {"speaker_labels": {"SPEAKER_00": "Sarah"}},
    })

    assert touched == 2
    assert mgr.get_pending("user1")[0].content == "Fuad: hi"
    assert mgr.get_archived("user1")[0].content == "Sarah: hi"


def test_update_transcriptions_batch_empty_updates_is_noop():
    mgr = make_manager()
    assert mgr.update_transcriptions_batch("user1", {}) == 0


def test_set_speaker_label_merges_without_dropping_other_local_speakers():
    mgr = make_manager()
    segments = [
        {"start": 0.0, "end": 1.0, "local_speaker": "SPEAKER_00", "text": "hi"},
        {"start": 1.0, "end": 2.0, "local_speaker": "SPEAKER_01", "text": "hello"},
    ]
    t = mgr.add_transcription("user1", render_segments(segments), segments=segments)
    mgr.set_speaker_label("user1", t.id, "SPEAKER_00", "Fuad")

    updated = mgr.set_speaker_label("user1", t.id, "SPEAKER_01", "Sarah")

    assert updated.speaker_labels == {"SPEAKER_00": "Fuad", "SPEAKER_01": "Sarah"}
    assert updated.content == "Fuad: hi\nSarah: hello"


def test_set_speaker_label_overwrites_an_existing_label():
    """A manual correction always wins, even over a previous manual/auto label."""
    mgr = make_manager()
    segments = [{"start": 0.0, "end": 1.0, "local_speaker": "SPEAKER_00", "text": "hi"}]
    t = mgr.add_transcription("user1", render_segments(segments), segments=segments,
                               speaker_labels={"SPEAKER_00": "Wrong Match"})

    updated = mgr.set_speaker_label("user1", t.id, "SPEAKER_00", "Fuad")

    assert updated.speaker_labels == {"SPEAKER_00": "Fuad"}


def test_add_speaker_labels_if_absent_skips_already_labeled_speakers():
    mgr = make_manager()
    segments = [
        {"start": 0.0, "end": 1.0, "local_speaker": "SPEAKER_00", "text": "hi"},
        {"start": 1.0, "end": 2.0, "local_speaker": "SPEAKER_01", "text": "hello"},
    ]
    t = mgr.add_transcription("user1", render_segments(segments), segments=segments,
                               speaker_labels={"SPEAKER_00": "Fuad"})

    touched = mgr.add_speaker_labels_if_absent("user1", {
        t.id: {"SPEAKER_00": "Someone Else", "SPEAKER_01": "Sarah"},
    })

    assert touched == 1
    assert mgr.get_pending("user1")[0].speaker_labels == {"SPEAKER_00": "Fuad", "SPEAKER_01": "Sarah"}


def test_add_speaker_labels_if_absent_never_clobbers_a_label_set_after_the_snapshot():
    """Reproduces the race the auto-tag rescan used to be vulnerable to: the
    caller computed `updates` from a stale snapshot (SPEAKER_00 unlabeled),
    but a manual edit landed in between and set it before this call runs.
    The absent-check must be re-done fresh under the lock, not trusted from
    the caller's snapshot, so the manual edit must survive untouched."""
    mgr = make_manager()
    segments = [{"start": 0.0, "end": 1.0, "local_speaker": "SPEAKER_00", "text": "hi"}]
    t = mgr.add_transcription("user1", render_segments(segments), segments=segments)

    # Simulates a manual edit landing after the rescan took its snapshot but
    # before it writes - set_speaker_label goes straight to disk here.
    mgr.set_speaker_label("user1", t.id, "SPEAKER_00", "Fuad")

    # Stale candidate from the rescan's earlier (pre-manual-edit) snapshot.
    touched = mgr.add_speaker_labels_if_absent("user1", {t.id: {"SPEAKER_00": "Wrong Auto Match"}})

    assert touched == 0
    assert mgr.get_pending("user1")[0].speaker_labels == {"SPEAKER_00": "Fuad"}


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
