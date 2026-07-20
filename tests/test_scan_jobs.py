"""Tests for src/managers/scan_jobs.py - the on-demand scan job registry."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers.scan_jobs import ScanJobRegistry, MAX_JOBS_PER_USER


@pytest.fixture
def registry():
    return ScanJobRegistry()


def test_new_job_starts_pending_with_one_target_per_topic(registry):
    job = registry.create("u1", "all", [("ai", "news"), ("AAPL", "stock")])

    assert job.status == "pending"
    assert [(t.topic, t.kind) for t in job.targets] == [("ai", "news"), ("AAPL", "stock")]
    assert all(t.state == "pending" for t in job.targets)


def test_job_is_retrievable_by_id(registry):
    job = registry.create("u1", "all", [("ai", "news")])

    assert registry.get(job.id) is job


def test_get_unknown_job_returns_none(registry):
    assert registry.get("no-such-job") is None


def test_only_one_job_may_be_active_per_user(registry):
    first = registry.create("u1", "all", [("ai", "news")])

    assert registry.active_for_user("u1") is first


def test_a_finished_job_no_longer_blocks_the_user(registry):
    job = registry.create("u1", "all", [("ai", "news")])
    job.finish()

    assert registry.active_for_user("u1") is None


def test_another_users_job_does_not_block(registry):
    registry.create("u1", "all", [("ai", "news")])

    assert registry.active_for_user("u2") is None


def test_finishing_a_job_marks_it_done_and_stamps_finished_at(registry):
    job = registry.create("u1", "all", [("ai", "news")])
    job.targets[0].state = "stored"
    job.finish()

    assert job.status == "done"
    assert job.finished_at is not None


def test_a_failed_target_does_not_fail_the_whole_job(registry):
    """One dead source shouldn't discard the insights the others produced."""
    job = registry.create("u1", "all", [("ai", "news"), ("AAPL", "stock")])
    job.targets[0].state = "stored"
    job.targets[1].state = "fetch_failed"
    job.targets[1].error = "yahoo timed out"
    job.finish()

    assert job.status == "done"
    assert job.targets[0].state == "stored"


def test_job_fails_only_when_the_run_itself_blows_up(registry):
    job = registry.create("u1", "all", [("ai", "news")])
    job.fail("registry exploded")

    assert job.status == "failed"
    assert job.error == "registry exploded"
    assert job.finished_at is not None
    assert registry.active_for_user("u1") is None


def test_old_jobs_are_evicted_per_user(registry):
    """Unbounded retention would leak for the lifetime of the process."""
    jobs = []
    for _ in range(MAX_JOBS_PER_USER + 5):
        job = registry.create("u1", "adhoc", [("x", "news")])
        job.finish()
        jobs.append(job)

    assert registry.get(jobs[-1].id) is not None
    assert registry.get(jobs[0].id) is None


def test_eviction_is_scoped_per_user(registry):
    """One noisy user must not evict another user's jobs."""
    theirs = registry.create("u2", "adhoc", [("x", "news")])
    theirs.finish()

    for _ in range(MAX_JOBS_PER_USER + 5):
        registry.create("u1", "adhoc", [("x", "news")]).finish()

    assert registry.get(theirs.id) is not None


def test_to_dict_is_json_safe(registry):
    job = registry.create("u1", "adhoc", [("TSLA", "stock")])
    job.targets[0].state = "stored"
    job.targets[0].insight_id = "abc-123"

    payload = job.to_dict()

    assert payload["status"] == "pending"
    assert payload["mode"] == "adhoc"
    assert payload["targets"] == [
        {"topic": "TSLA", "kind": "stock", "state": "stored", "insight_id": "abc-123", "error": None}
    ]
