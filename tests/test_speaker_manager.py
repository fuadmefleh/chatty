"""Tests for SpeakerManager (named voice roster + matching)."""
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.speakers.speaker_manager import SpeakerManager


def make_manager():
    tmpdir = tempfile.mkdtemp()
    return SpeakerManager(data_dir=tmpdir)


def unit_vector(seed: int, dim: int = 8):
    rng = np.random.RandomState(seed)
    v = rng.randn(dim)
    return (v / np.linalg.norm(v)).tolist()


def test_create_and_list_speaker():
    mgr = make_manager()
    embedding = unit_vector(1)

    speaker = mgr.create_speaker("user1", "Fuad", embedding, transcription_id="t1", start=0.0, end=2.0)

    listed = mgr.list_speakers("user1")
    assert len(listed) == 1
    assert listed[0]["id"] == speaker["id"]
    assert listed[0]["name"] == "Fuad"
    assert listed[0]["num_samples"] == 1
    assert listed[0]["sample_transcription_id"] == "t1"
    # Public shape never exposes raw embeddings.
    assert "embedding" not in listed[0]
    assert "samples" not in listed[0]


def test_speakers_scoped_per_user():
    mgr = make_manager()
    mgr.create_speaker("user1", "Fuad", unit_vector(1))
    mgr.create_speaker("user2", "Sarah", unit_vector(2))

    assert [s["name"] for s in mgr.list_speakers("user1")] == ["Fuad"]
    assert [s["name"] for s in mgr.list_speakers("user2")] == ["Sarah"]


def test_match_finds_same_voice_above_threshold():
    mgr = make_manager()
    embedding = unit_vector(1)
    mgr.create_speaker("user1", "Fuad", embedding)

    match = mgr.match("user1", embedding)

    assert match is not None
    speaker, score = match
    assert speaker["name"] == "Fuad"
    assert score > 0.99  # identical vector


def test_match_returns_none_for_unrelated_voice():
    mgr = make_manager()
    mgr.create_speaker("user1", "Fuad", unit_vector(1))

    match = mgr.match("user1", unit_vector(2))

    assert match is None


def test_match_returns_none_when_roster_is_empty():
    mgr = make_manager()
    assert mgr.match("user1", unit_vector(1)) is None


def test_add_sample_grows_roster_entry_and_improves_match_pool():
    mgr = make_manager()
    speaker = mgr.create_speaker("user1", "Fuad", unit_vector(1))

    updated = mgr.add_sample("user1", speaker["id"], unit_vector(3), transcription_id="t2")

    assert len(updated["samples"]) == 2
    assert mgr.list_speakers("user1")[0]["num_samples"] == 2


def test_add_sample_unknown_speaker_returns_none():
    mgr = make_manager()
    assert mgr.add_sample("user1", "no-such-id", unit_vector(1)) is None


def test_rename_speaker():
    mgr = make_manager()
    speaker = mgr.create_speaker("user1", "Fuad", unit_vector(1))

    renamed = mgr.rename_speaker("user1", speaker["id"], "Fuad Mefleh")

    assert renamed["name"] == "Fuad Mefleh"
    assert mgr.list_speakers("user1")[0]["name"] == "Fuad Mefleh"


def test_rename_unknown_speaker_returns_none():
    mgr = make_manager()
    assert mgr.rename_speaker("user1", "no-such-id", "New Name") is None


def test_delete_speaker_removes_from_roster():
    mgr = make_manager()
    speaker = mgr.create_speaker("user1", "Fuad", unit_vector(1))

    assert mgr.delete_speaker("user1", speaker["id"]) is True
    assert mgr.list_speakers("user1") == []


def test_delete_unknown_speaker_returns_false():
    mgr = make_manager()
    assert mgr.delete_speaker("user1", "no-such-id") is False
