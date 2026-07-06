"""Tests for skills/pi_agent/requests_manager.py's FeatureRequestsManager,
focused on list_pending_merges() (used by self_upgrade_manager.py's
retry_pending_merges to find merges deferred by the dirty-main safety gate).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.pi_agent.requests_manager import FeatureRequestsManager


def make_manager(tmp_path) -> FeatureRequestsManager:
    return FeatureRequestsManager(data_dir=str(tmp_path / "feature_requests"))


def test_list_pending_merges_empty_when_none_pending(tmp_path):
    mgr = make_manager(tmp_path)
    mgr.create("do something")
    assert mgr.list_pending_merges() == []


def test_list_pending_merges_filters_to_that_status_only(tmp_path):
    mgr = make_manager(tmp_path)
    queued = mgr.create("still queued")
    pending = mgr.create("waiting on a clean main")
    mgr.update(pending.id, status="merge_pending", branch="feature-request/x-1")
    mgr.update(queued.id, status="queued")

    done = mgr.create("already merged")
    mgr.update(done.id, status="completed")

    result = mgr.list_pending_merges()
    assert [r.id for r in result] == [pending.id]
    assert result[0].branch == "feature-request/x-1"


def test_list_pending_merges_sorted_oldest_first(tmp_path):
    mgr = make_manager(tmp_path)
    first = mgr.create("first stuck request")
    second = mgr.create("second stuck request")
    # Created in this order, so `first` already has an earlier created_at -
    # update both to merge_pending without touching created_at.
    mgr.update(first.id, status="merge_pending")
    mgr.update(second.id, status="merge_pending")

    result = mgr.list_pending_merges()
    assert [r.id for r in result] == [first.id, second.id]
