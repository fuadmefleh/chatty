"""Tests for the speaker roster + per-transcript labeling endpoints
(GET/PUT/DELETE /api/chatty/speakers, GET .../segments, POST .../label)."""
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import chatty_web_server as server
from skills.speakers.speaker_manager import SpeakerManager
from skills.transcriptions.transcriptions_manager import TranscriptionsManager
from src.web import config, state


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture(autouse=True)
def isolated_managers(monkeypatch):
    monkeypatch.setattr(state, "transcriptions_manager", TranscriptionsManager(data_dir=tempfile.mkdtemp()))
    monkeypatch.setattr(state, "speaker_manager", SpeakerManager(data_dir=tempfile.mkdtemp()))
    monkeypatch.setattr(config, "WEB_USER_ID", "web_user")
    yield


def auth_headers():
    return {"X-API-Key": config.API_KEY}


def unit_vector(seed: int, dim: int = 8):
    rng = np.random.RandomState(seed)
    v = rng.randn(dim)
    return (v / np.linalg.norm(v)).tolist()


def make_transcription_with_segments(embeddings=None):
    """Directly seed a transcription with structured segments/embeddings,
    the shape ingestion produces once a real STT response comes back."""
    segments = [
        {"start": 0.0, "end": 2.0, "local_speaker": "SPEAKER_00", "text": "hi there"},
        {"start": 2.0, "end": 4.0, "local_speaker": "SPEAKER_01", "text": "hello back"},
    ]
    embeddings = embeddings or {"SPEAKER_00": unit_vector(1), "SPEAKER_01": unit_vector(2)}
    return state.transcriptions_manager.add_transcription(
        "web_user", "SPEAKER_00: hi there\nSPEAKER_01: hello back",
        segments=segments, speaker_embeddings=embeddings,
    )


def test_speakers_list_starts_empty(client):
    resp = client.get("/api/chatty/speakers", headers=auth_headers())
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_segments_for_unknown_transcription_404s(client):
    resp = client.get("/api/chatty/transcriptions/no-such-id/segments", headers=auth_headers())
    assert resp.status_code == 404


def test_get_segments_returns_structured_shape(client):
    t = make_transcription_with_segments()

    resp = client.get(f"/api/chatty/transcriptions/{t.id}/segments", headers=auth_headers())

    assert resp.status_code == 200
    segments = resp.json()["segments"]
    assert len(segments) == 2
    assert segments[0]["local_speaker"] == "SPEAKER_00"
    assert segments[0]["speaker_name"] is None
    assert segments[0]["text"] == "hi there"


def test_label_with_new_name_creates_speaker_and_updates_content(client):
    t = make_transcription_with_segments()

    resp = client.post(
        f"/api/chatty/transcriptions/{t.id}/label",
        headers=auth_headers(),
        json={"local_speaker": "SPEAKER_00", "name": "Fuad"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["speaker"]["name"] == "Fuad"
    assert body["also_updated_count"] == 0

    roster = client.get("/api/chatty/speakers", headers=auth_headers()).json()
    assert len(roster) == 1
    assert roster[0]["name"] == "Fuad"

    pending = client.get("/api/chatty/transcriptions", headers=auth_headers()).json()
    labeled = next(p for p in pending if p["id"] == t.id)
    assert "Fuad: hi there" in labeled["content"]
    assert "SPEAKER_01: hello back" in labeled["content"]


def test_label_retroactively_relabels_other_transcripts_with_same_voice(client):
    shared_embedding = unit_vector(42)
    t1 = make_transcription_with_segments({"SPEAKER_00": shared_embedding, "SPEAKER_01": unit_vector(2)})
    t2 = make_transcription_with_segments({"SPEAKER_00": shared_embedding, "SPEAKER_01": unit_vector(3)})

    resp = client.post(
        f"/api/chatty/transcriptions/{t1.id}/label",
        headers=auth_headers(),
        json={"local_speaker": "SPEAKER_00", "name": "Fuad"},
    )

    assert resp.json()["also_updated_count"] == 1

    pending = client.get("/api/chatty/transcriptions", headers=auth_headers()).json()
    other = next(p for p in pending if p["id"] == t2.id)
    assert "Fuad: hi there" in other["content"]


def test_label_with_existing_speaker_id_adds_sample_instead_of_creating_new(client):
    t1 = make_transcription_with_segments()
    create_resp = client.post(
        f"/api/chatty/transcriptions/{t1.id}/label",
        headers=auth_headers(),
        json={"local_speaker": "SPEAKER_00", "name": "Fuad"},
    )
    speaker_id = create_resp.json()["speaker"]["id"]

    t2 = make_transcription_with_segments()
    resp = client.post(
        f"/api/chatty/transcriptions/{t2.id}/label",
        headers=auth_headers(),
        json={"local_speaker": "SPEAKER_00", "speaker_id": speaker_id},
    )

    assert resp.status_code == 200
    roster = client.get("/api/chatty/speakers", headers=auth_headers()).json()
    assert len(roster) == 1  # no duplicate speaker created
    assert roster[0]["num_samples"] == 2


def test_label_without_name_or_speaker_id_rejected(client):
    t = make_transcription_with_segments()
    resp = client.post(
        f"/api/chatty/transcriptions/{t.id}/label",
        headers=auth_headers(),
        json={"local_speaker": "SPEAKER_00"},
    )
    assert resp.status_code == 400


def test_label_unknown_local_speaker_rejected(client):
    t = make_transcription_with_segments()
    resp = client.post(
        f"/api/chatty/transcriptions/{t.id}/label",
        headers=auth_headers(),
        json={"local_speaker": "SPEAKER_99", "name": "Fuad"},
    )
    assert resp.status_code == 400


def test_label_unknown_transcription_404s(client):
    resp = client.post(
        "/api/chatty/transcriptions/no-such-id/label",
        headers=auth_headers(),
        json={"local_speaker": "SPEAKER_00", "name": "Fuad"},
    )
    assert resp.status_code == 404


def test_rename_speaker(client):
    t = make_transcription_with_segments()
    create_resp = client.post(
        f"/api/chatty/transcriptions/{t.id}/label",
        headers=auth_headers(),
        json={"local_speaker": "SPEAKER_00", "name": "Fuad"},
    )
    speaker_id = create_resp.json()["speaker"]["id"]

    resp = client.put(f"/api/chatty/speakers/{speaker_id}", headers=auth_headers(), json={"name": "Fuad Mefleh"})

    assert resp.status_code == 200
    assert resp.json()["name"] == "Fuad Mefleh"


def test_rename_unknown_speaker_404s(client):
    resp = client.put("/api/chatty/speakers/no-such-id", headers=auth_headers(), json={"name": "New Name"})
    assert resp.status_code == 404


def test_delete_speaker_does_not_strip_existing_labels(client):
    t = make_transcription_with_segments()
    create_resp = client.post(
        f"/api/chatty/transcriptions/{t.id}/label",
        headers=auth_headers(),
        json={"local_speaker": "SPEAKER_00", "name": "Fuad"},
    )
    speaker_id = create_resp.json()["speaker"]["id"]

    del_resp = client.delete(f"/api/chatty/speakers/{speaker_id}", headers=auth_headers())
    assert del_resp.status_code == 200
    assert client.get("/api/chatty/speakers", headers=auth_headers()).json() == []

    # Deleting from the roster is not retroactive - the already-applied label stays.
    pending = client.get("/api/chatty/transcriptions", headers=auth_headers()).json()
    labeled = next(p for p in pending if p["id"] == t.id)
    assert "Fuad: hi there" in labeled["content"]


def test_delete_unknown_speaker_404s(client):
    resp = client.delete("/api/chatty/speakers/no-such-id", headers=auth_headers())
    assert resp.status_code == 404


def test_manual_rescan_picks_up_transcripts_missed_by_the_automatic_one(client):
    # Simulate the real scenario: threshold was too strict when t1 was
    # labeled (t2's matching voice didn't clear it and got skipped by the
    # automatic post-label rescan), then the threshold is loosened and the
    # user triggers a manual rescan to sweep up what was missed.
    shared_embedding = unit_vector(42)
    t1 = make_transcription_with_segments({"SPEAKER_00": shared_embedding, "SPEAKER_01": unit_vector(2)})
    t2 = make_transcription_with_segments({"SPEAKER_00": shared_embedding, "SPEAKER_01": unit_vector(3)})

    import skills.speakers.speaker_manager as speaker_manager_module
    original_threshold = speaker_manager_module.SPEAKER_MATCH_THRESHOLD
    speaker_manager_module.SPEAKER_MATCH_THRESHOLD = 2.0  # impossible to clear - forces a miss
    try:
        label_resp = client.post(
            f"/api/chatty/transcriptions/{t1.id}/label",
            headers=auth_headers(),
            json={"local_speaker": "SPEAKER_00", "name": "Fuad"},
        )
        assert label_resp.json()["also_updated_count"] == 0
    finally:
        speaker_manager_module.SPEAKER_MATCH_THRESHOLD = original_threshold  # "loosen" the threshold

    rescan_resp = client.post("/api/chatty/speakers/rescan", headers=auth_headers())

    assert rescan_resp.status_code == 200
    assert rescan_resp.json()["updated_count"] == 1
    pending = client.get("/api/chatty/transcriptions", headers=auth_headers()).json()
    other = next(p for p in pending if p["id"] == t2.id)
    assert "Fuad: hi there" in other["content"]


def test_manual_rescan_with_no_roster_is_a_noop(client):
    make_transcription_with_segments()
    resp = client.post("/api/chatty/speakers/rescan", headers=auth_headers())
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 0
