"""Tests for the video production web endpoints and video_manager."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
import chatty_web_server
from skills.video_production import video_manager


@pytest.fixture(autouse=True)
def clean_jobs_dir(tmp_path, monkeypatch):
    """Redirect video_jobs storage to a temp directory for each test."""
    jobs_dir = tmp_path / "data" / "video_jobs"
    jobs_dir.mkdir(parents=True)
    jobs_file = jobs_dir / "jobs.json"

    # Patch the module-level constants
    monkeypatch.setattr(video_manager, "_JOBS_DIR", jobs_dir)
    monkeypatch.setattr(video_manager, "_JOBS_FILE", jobs_file)
    return jobs_file


@pytest.fixture
def api_key(monkeypatch):
    key = "test-key-123"
    monkeypatch.setattr(chatty_web_server, "API_KEY", key)
    return key


@pytest.fixture
def client():
    return TestClient(chatty_web_server.app, base_url="http://test")


def _auth_headers(api_key):
    return {"X-API-Key": api_key}


# -- video_manager tests --


def test_create_job_returns_record(clean_jobs_dir):
    job = video_manager.create_job("a cat astronaut", duration_seconds=6, resolution="720p")
    assert job["id"] is not None
    assert job["prompt"] == "a cat astronaut"
    assert job["duration_seconds"] == 6
    assert job["resolution"] == "720p"
    assert job["status"] == "submitted"
    assert job["url"] is None
    assert job["error"] is None


def test_list_jobs_returns_created_job(clean_jobs_dir):
    video_manager.create_job("first")
    video_manager.create_job("second")
    jobs = video_manager.list_jobs()
    assert len(jobs) == 2
    # Most recent first
    assert jobs[0]["prompt"] == "second"
    assert jobs[1]["prompt"] == "first"


def test_list_jobs_respects_limit(clean_jobs_dir):
    for i in range(5):
        video_manager.create_job(f"job-{i}")
    jobs = video_manager.list_jobs(limit=3)
    assert len(jobs) == 3


def test_get_job_returns_existing(clean_jobs_dir):
    created = video_manager.create_job("find me")
    found = video_manager.get_job(created["id"])
    assert found is not None
    assert found["id"] == created["id"]


def test_get_job_returns_none_for_missing(clean_jobs_dir):
    result = video_manager.get_job("nonexistent")
    assert result is None


def test_update_job_updates_fields(clean_jobs_dir):
    created = video_manager.create_job("update me")
    updated = video_manager.update_job(created["id"], status="completed", url="http://example.com/video.mp4")
    assert updated is not None
    assert updated["status"] == "completed"
    assert updated["url"] == "http://example.com/video.mp4"
    # Original prompt preserved
    assert updated["prompt"] == "update me"


def test_update_job_returns_none_for_missing(clean_jobs_dir):
    result = video_manager.update_job("nonexistent", status="completed")
    assert result is None


def test_delete_job_removes_record(clean_jobs_dir):
    created = video_manager.create_job("delete me")
    assert video_manager.delete_job(created["id"]) is True
    assert video_manager.get_job(created["id"]) is None


def test_delete_job_returns_false_for_missing(clean_jobs_dir):
    assert video_manager.delete_job("nonexistent") is False


def test_jobs_persist_across_calls(clean_jobs_dir):
    created = video_manager.create_job("persist")
    # Re-read from file
    jobs = video_manager.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["id"] == created["id"]


# -- web endpoint tests --


def test_get_video_jobs_empty(client, api_key):
    resp = client.get("/api/chatty/video-jobs", headers=_auth_headers(api_key))
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_video_jobs_returns_jobs(client, api_key):
    video_manager.create_job("first")
    resp = client.get("/api/chatty/video-jobs", headers=_auth_headers(api_key))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["prompt"] == "first"


def test_get_video_jobs_requires_auth(client):
    resp = client.get("/api/chatty/video-jobs")
    assert resp.status_code in (401, 403)


def test_create_video_job(client, api_key):
    resp = client.post(
        "/api/chatty/video-jobs",
        json={"prompt": "a dancing robot", "duration_seconds": 6, "resolution": "1080p"},
        headers=_auth_headers(api_key),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["prompt"] == "a dancing robot"
    assert data["duration_seconds"] == 6
    assert data["resolution"] == "1080p"
    assert data["status"] == "submitted"


def test_create_video_job_defaults(client, api_key):
    resp = client.post(
        "/api/chatty/video-jobs",
        json={"prompt": "simple video"},
        headers=_auth_headers(api_key),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["duration_seconds"] == 4
    assert data["resolution"] == "auto"


def test_create_video_job_empty_prompt_rejected(client, api_key):
    resp = client.post(
        "/api/chatty/video-jobs",
        json={"prompt": "   "},
        headers=_auth_headers(api_key),
    )
    assert resp.status_code == 400


def test_create_video_job_invalid_duration(client, api_key):
    resp = client.post(
        "/api/chatty/video-jobs",
        json={"prompt": "test", "duration_seconds": 99},
        headers=_auth_headers(api_key),
    )
    assert resp.status_code == 400


def test_create_video_job_invalid_resolution(client, api_key):
    resp = client.post(
        "/api/chatty/video-jobs",
        json={"prompt": "test", "resolution": "4k"},
        headers=_auth_headers(api_key),
    )
    assert resp.status_code == 400


def test_get_single_video_job(client, api_key):
    created = video_manager.create_job("single")
    resp = client.get(f"/api/chatty/video-jobs/{created['id']}", headers=_auth_headers(api_key))
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_single_video_job_not_found(client, api_key):
    resp = client.get("/api/chatty/video-jobs/nonexistent", headers=_auth_headers(api_key))
    assert resp.status_code == 404


def test_delete_video_job(client, api_key):
    created = video_manager.create_job("to delete")
    resp = client.delete(f"/api/chatty/video-jobs/{created['id']}", headers=_auth_headers(api_key))
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


def test_delete_video_job_not_found(client, api_key):
    resp = client.delete("/api/chatty/video-jobs/nonexistent", headers=_auth_headers(api_key))
    assert resp.status_code == 404


# -- background generation integration --


@patch("chatty_web_server._video_api")
def test_create_video_job_generates_success(mock_video_api, client, api_key):
    """Verify that creating a job triggers generation and updates status on success."""
    mock_video_api.generate_video = AsyncMock(return_value={"success": True, "url": "/api/chatty/chat-media/test.mp4?api_key=abc"})
    resp = client.post(
        "/api/chatty/video-jobs",
        json={"prompt": "generation test"},
        headers=_auth_headers(api_key),
    )
    assert resp.status_code == 201
    job_id = resp.json()["id"]
    # BackgroundTasks run synchronously in TestClient, so the job should be updated
    job = video_manager.get_job(job_id)
    assert job["status"] == "completed"
    assert "test.mp4" in job["url"]


@patch("chatty_web_server._video_api")
def test_create_video_job_generates_failure(mock_video_api, client, api_key):
    """Verify that a failed generation is recorded in the job."""
    mock_video_api.generate_video = AsyncMock(return_value={"success": False, "error": "API error"})
    resp = client.post(
        "/api/chatty/video-jobs",
        json={"prompt": "fail test"},
        headers=_auth_headers(api_key),
    )
    assert resp.status_code == 201
    job_id = resp.json()["id"]
    job = video_manager.get_job(job_id)
    assert job["status"] == "failed"
    assert "API error" in job["error"]


@patch("chatty_web_server._video_api")
def test_create_video_job_generation_exception(mock_video_api, client, api_key):
    """Verify that exceptions during generation are caught and recorded."""
    mock_video_api.generate_video = AsyncMock(side_effect=RuntimeError("network down"))
    resp = client.post(
        "/api/chatty/video-jobs",
        json={"prompt": "exception test"},
        headers=_auth_headers(api_key),
    )
    assert resp.status_code == 201
    job_id = resp.json()["id"]
    job = video_manager.get_job(job_id)
    assert job["status"] == "failed"
    assert "network down" in job["error"]
