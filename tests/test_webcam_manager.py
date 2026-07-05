"""Tests for src/managers/webcam_manager.py - the webcam source list and
its companion discovery-suggestion queue."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers import webcam_manager as wm


def make_sources_manager(tmp_path):
    return wm.WebcamSourcesManager(data_dir=str(tmp_path / "webcam_sources"))


def make_suggestions_manager(tmp_path):
    return wm.WebcamSuggestionsManager(data_dir=str(tmp_path / "webcam_sources"))


def test_source_create_and_list_newest_first(tmp_path):
    mgr = make_sources_manager(tmp_path)
    first = mgr.create(name="Cam A", url="https://a.example/cam")
    second = mgr.create(name="Cam B", url="https://b.example/cam", kind="snapshot", location="NYC")

    listed = mgr.list()
    assert [s.id for s in listed] == [second.id, first.id]
    assert listed[0].kind == "snapshot"
    assert listed[0].location == "NYC"
    assert listed[0].enabled is True
    assert listed[0].source == "manual"


def test_source_invalid_kind_falls_back_to_webpage(tmp_path):
    mgr = make_sources_manager(tmp_path)
    s = mgr.create(name="Cam", url="https://x.example", kind="not-a-real-kind")
    assert s.kind == "webpage"


def test_source_get_update_delete(tmp_path):
    mgr = make_sources_manager(tmp_path)
    s = mgr.create(name="Cam", url="https://x.example")

    assert mgr.get(s.id).id == s.id
    assert mgr.get("nope") is None

    updated = mgr.update(s.id, enabled=False, name="Renamed")
    assert updated.enabled is False
    assert updated.name == "Renamed"
    assert mgr.get(s.id).enabled is False

    # Updating to an invalid kind is silently ignored rather than corrupting state.
    unchanged = mgr.update(s.id, kind="bogus")
    assert unchanged.kind == "webpage"

    assert mgr.delete(s.id) is True
    assert mgr.get(s.id) is None
    assert mgr.delete(s.id) is False


def test_suggestion_create_and_list_newest_first(tmp_path):
    mgr = make_suggestions_manager(tmp_path)
    first = mgr.create(name="Cam A", url="https://a.example", discovered_url="https://reddit.com/a")
    second = mgr.create(name="Cam B", url="https://b.example", discovered_url="https://reddit.com/b")

    listed = mgr.list()
    assert [s.id for s in listed] == [second.id, first.id]
    assert listed[0].status == "pending"


def test_suggestion_get_update_delete(tmp_path):
    mgr = make_suggestions_manager(tmp_path)
    s = mgr.create(name="Cam", url="https://x.example", discovered_url="https://reddit.com/x")

    assert mgr.get(s.id).id == s.id
    assert mgr.get("nope") is None

    updated = mgr.update(s.id, status="approved", source_id="src-1")
    assert updated.status == "approved"
    assert updated.source_id == "src-1"
    assert mgr.get(s.id).status == "approved"

    assert mgr.delete(s.id) is True
    assert mgr.get(s.id) is None
    assert mgr.delete(s.id) is False


def test_suggestion_list_by_status(tmp_path):
    mgr = make_suggestions_manager(tmp_path)
    pending = mgr.create(name="A", url="u1", discovered_url="d1")
    dismissed = mgr.create(name="B", url="u2", discovered_url="d2")
    mgr.update(dismissed.id, status="dismissed")

    assert [s.id for s in mgr.list_by_status("pending")] == [pending.id]
    assert [s.id for s in mgr.list_by_status("dismissed")] == [dismissed.id]


def test_seen_discovered_urls_includes_every_status(tmp_path):
    mgr = make_suggestions_manager(tmp_path)
    mgr.create(name="A", url="u1", discovered_url="d1")
    s2 = mgr.create(name="B", url="u2", discovered_url="d2")
    mgr.update(s2.id, status="dismissed")

    assert wm.WebcamSuggestionsManager(data_dir=mgr.data_dir).seen_discovered_urls() == {"d1", "d2"}
