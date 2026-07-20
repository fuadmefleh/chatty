"""Tests for the on-demand insights scan endpoints.

POST /api/chatty/insights/scan       - start a background scan
GET  /api/chatty/insights/scan/{id}  - poll its progress
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import chatty_web_server as server
from src.web import config, state
from src.managers.scan_jobs import ScanJobRegistry
from src.managers.world_watch import ScanResult
from skills.watchlist.watchlist_manager import WatchTopic


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture(autouse=True)
def fresh_registry():
    """Each test gets its own registry - jobs are process-lifetime state."""
    original = state.scan_jobs
    state.scan_jobs = ScanJobRegistry()
    yield state.scan_jobs
    state.scan_jobs = original


def _headers():
    return {"X-API-Key": config.API_KEY}


def make_topic(topic="ai", kind="news", topic_id="t1"):
    return WatchTopic(
        topic_id=topic_id, topic=topic, user_id=config.WEB_USER_ID,
        created_at="2026-07-01T00:00:00", kind=kind,
    )


def patch_scan(result_state="stored"):
    """Stub scan_topic where the router looks it up."""
    return patch(
        "src.managers.world_watch.scan_topic",
        new_callable=AsyncMock,
        return_value=ScanResult(state=result_state, topic="ai", kind="news",
                                insight=MagicMock(id="ins-1")),
    )


def patch_topics(topics):
    return patch.object(state, "watchlist_manager", MagicMock(
        get_topics=MagicMock(return_value=topics),
        get_topic_by_id=MagicMock(return_value=topics[0] if topics else None),
    ))


# ── Auth ─────────────────────────────────────────────────────────────────────

def test_scan_requires_api_key(client):
    resp = client.post("/api/chatty/insights/scan", json={"mode": "all"}, headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


# ── Starting a scan ──────────────────────────────────────────────────────────

def test_scan_all_returns_202_with_a_job_id(client):
    with patch_topics([make_topic()]), patch_scan():
        resp = client.post("/api/chatty/insights/scan", json={"mode": "all"}, headers=_headers())

    assert resp.status_code == 202
    assert "job_id" in resp.json()


def test_scan_all_enumerates_every_watchlist_topic(client, fresh_registry):
    topics = [make_topic("ai", "news", "t1"), make_topic("AAPL", "stock", "t2")]

    with patch_topics(topics), patch_scan():
        resp = client.post("/api/chatty/insights/scan", json={"mode": "all"}, headers=_headers())

    job = fresh_registry.get(resp.json()["job_id"])
    assert [(t.topic, t.kind) for t in job.targets] == [("ai", "news"), ("AAPL", "stock")]


def test_scan_topic_targets_only_that_topic(client, fresh_registry):
    with patch_topics([make_topic("ai", "news", "t1")]), patch_scan():
        resp = client.post(
            "/api/chatty/insights/scan", json={"mode": "topic", "topic_id": "t1"}, headers=_headers()
        )

    job = fresh_registry.get(resp.json()["job_id"])
    assert [(t.topic, t.kind) for t in job.targets] == [("ai", "news")]


def test_scan_unknown_topic_id_is_404(client):
    with patch.object(state, "watchlist_manager", MagicMock(get_topic_by_id=MagicMock(return_value=None))):
        resp = client.post(
            "/api/chatty/insights/scan", json={"mode": "topic", "topic_id": "nope"}, headers=_headers()
        )

    assert resp.status_code == 404


def test_adhoc_scan_uses_the_submitted_topic_and_kind(client, fresh_registry):
    with patch_scan():
        resp = client.post(
            "/api/chatty/insights/scan",
            json={"mode": "adhoc", "topic": "TSLA", "kind": "stock"},
            headers=_headers(),
        )

    job = fresh_registry.get(resp.json()["job_id"])
    assert [(t.topic, t.kind) for t in job.targets] == [("TSLA", "stock")]


def test_adhoc_scan_passes_ad_hoc_to_the_pipeline(client):
    with patch_scan() as scan:
        client.post(
            "/api/chatty/insights/scan",
            json={"mode": "adhoc", "topic": "TSLA", "kind": "stock"},
            headers=_headers(),
        )

    assert scan.await_args.kwargs["ad_hoc"] is True


def test_watchlist_scan_does_not_pass_ad_hoc(client):
    with patch_topics([make_topic()]), patch_scan() as scan:
        client.post("/api/chatty/insights/scan", json={"mode": "all"}, headers=_headers())

    assert scan.await_args.kwargs["ad_hoc"] is False


# ── Validation ───────────────────────────────────────────────────────────────

def test_adhoc_requires_a_topic(client):
    resp = client.post(
        "/api/chatty/insights/scan", json={"mode": "adhoc", "kind": "news"}, headers=_headers()
    )
    assert resp.status_code == 422


def test_adhoc_rejects_an_unknown_kind(client):
    resp = client.post(
        "/api/chatty/insights/scan",
        json={"mode": "adhoc", "topic": "x", "kind": "telepathy"},
        headers=_headers(),
    )
    assert resp.status_code == 422


def test_unknown_mode_is_rejected(client):
    resp = client.post("/api/chatty/insights/scan", json={"mode": "vibes"}, headers=_headers())
    assert resp.status_code == 422


def test_scan_all_with_an_empty_watchlist_is_400(client):
    """Nothing to scan is a user-facing mistake, not an empty success."""
    with patch_topics([]):
        resp = client.post("/api/chatty/insights/scan", json={"mode": "all"}, headers=_headers())

    assert resp.status_code == 400


# ── Concurrency ──────────────────────────────────────────────────────────────

def test_a_second_concurrent_scan_is_rejected(client, fresh_registry):
    """A double-click must not fire duplicate LLM calls."""
    existing = fresh_registry.create(config.WEB_USER_ID, "all", [("ai", "news")])
    existing.start()

    with patch_topics([make_topic()]):
        resp = client.post("/api/chatty/insights/scan", json={"mode": "all"}, headers=_headers())

    assert resp.status_code == 409
    assert resp.json()["detail"]["job_id"] == existing.id


def test_a_finished_scan_does_not_block_the_next_one(client, fresh_registry):
    fresh_registry.create(config.WEB_USER_ID, "all", [("ai", "news")]).finish()

    with patch_topics([make_topic()]), patch_scan():
        resp = client.post("/api/chatty/insights/scan", json={"mode": "all"}, headers=_headers())

    assert resp.status_code == 202


# ── Polling ──────────────────────────────────────────────────────────────────

def test_job_status_reports_per_target_progress(client, fresh_registry):
    with patch_topics([make_topic()]), patch_scan():
        job_id = client.post(
            "/api/chatty/insights/scan", json={"mode": "all"}, headers=_headers()
        ).json()["job_id"]

    resp = client.get(f"/api/chatty/insights/scan/{job_id}", headers=_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == job_id
    assert body["targets"][0]["topic"] == "ai"


def test_completed_job_records_the_stored_insight_id(client, fresh_registry):
    with patch_topics([make_topic()]), patch_scan():
        job_id = client.post(
            "/api/chatty/insights/scan", json={"mode": "all"}, headers=_headers()
        ).json()["job_id"]

    body = client.get(f"/api/chatty/insights/scan/{job_id}", headers=_headers()).json()

    assert body["status"] == "done"
    assert body["targets"][0]["state"] == "stored"
    assert body["targets"][0]["insight_id"] == "ins-1"


def test_a_failing_target_is_recorded_without_failing_the_job(client, fresh_registry):
    with patch_topics([make_topic()]), \
         patch("src.managers.world_watch.scan_topic", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
        job_id = client.post(
            "/api/chatty/insights/scan", json={"mode": "all"}, headers=_headers()
        ).json()["job_id"]

    body = client.get(f"/api/chatty/insights/scan/{job_id}", headers=_headers()).json()

    assert body["status"] == "done"
    assert body["targets"][0]["state"] == "error"
    assert "boom" in body["targets"][0]["error"]


def test_unknown_job_is_404(client):
    resp = client.get("/api/chatty/insights/scan/no-such-job", headers=_headers())
    assert resp.status_code == 404


# ── Feed filtering ───────────────────────────────────────────────────────────

def test_insights_feed_excludes_ad_hoc_by_default(client):
    with patch.object(state, "insights_manager", MagicMock(get_insights=MagicMock(return_value=[]))) as mgr:
        client.get("/api/chatty/insights", headers=_headers())

    assert mgr.get_insights.call_args.kwargs["include_ad_hoc"] is False


def test_insights_feed_can_include_ad_hoc(client):
    with patch.object(state, "insights_manager", MagicMock(get_insights=MagicMock(return_value=[]))) as mgr:
        client.get("/api/chatty/insights?include_ad_hoc=true", headers=_headers())

    assert mgr.get_insights.call_args.kwargs["include_ad_hoc"] is True
