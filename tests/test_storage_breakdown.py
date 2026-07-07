"""Tests for GET /api/chatty/health/storage-breakdown (disk usage breakdown)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import chatty_web_server as server


@pytest.fixture
def client():
    return TestClient(server.app)


def _headers():
    return {"X-API-Key": server.API_KEY}


def test_wrong_api_key_rejected(client):
    resp = client.get("/api/chatty/health/storage-breakdown", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


# ── _get_storage_breakdown unit tests ────────────────────────────────────────

def test_get_storage_breakdown_missing_path():
    result = server._get_storage_breakdown("/nonexistent/path/xyz", depth=1)
    assert result == []


def test_get_storage_breakdown_depth_0():
    """depth=0 returns only the mountpoint total."""
    mock_stdout = "1048576\t/tmp\n"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = mock_stdout

    with patch("subprocess.run", return_value=mock_result):
        result = server._get_storage_breakdown("/tmp", depth=0)

    assert len(result) == 1
    assert result[0]["path"] == "/tmp"
    assert result[0]["size_bytes"] == 1048576
    assert result[0]["depth"] == 0


def test_get_storage_breakdown_depth_1():
    """depth=1 returns mountpoint + immediate children."""
    mock_stdout = (
        "2097152\t/tmp/cache\n"
        "1048576\t/tmp/logs\n"
        "3145728\t/tmp\n"
    )
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = mock_stdout

    with patch("subprocess.run", return_value=mock_result):
        result = server._get_storage_breakdown("/tmp", depth=1)

    assert len(result) == 3
    # Root mountpoint should be first
    assert result[0]["path"] == "/tmp"
    # Then sorted by size desc
    assert result[1]["size_bytes"] >= result[2]["size_bytes"]


def test_get_storage_breakdown_depth_1_calculation():
    """Depth is calculated relative to mountpoint."""
    mock_stdout = (
        "2097152\t/tmp/cache\n"
        "1048576\t/tmp/logs\n"
        "3145728\t/tmp\n"
    )
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = mock_stdout

    with patch("subprocess.run", return_value=mock_result):
        result = server._get_storage_breakdown("/tmp", depth=1)

    # /tmp should be depth 0 (the mountpoint itself)
    root_entry = [r for r in result if r["path"] == "/tmp"][0]
    assert root_entry["depth"] == 0
    # /tmp/cache should be depth 1
    cache_entry = [r for r in result if r["path"] == "/tmp/cache"][0]
    assert cache_entry["depth"] == 1


def test_get_storage_breakdown_subprocess_timeout():
    """TimeoutExpired is caught and empty result returned."""
    import subprocess as submod
    with patch("subprocess.run", side_effect=submod.TimeoutExpired("du", 60)):
        result = server._get_storage_breakdown("/tmp", depth=1)
    assert result == []


# ── Endpoint integration tests ───────────────────────────────────────────────

def test_storage_breakdown_endpoint_no_mountpoint(client):
    """Without mountpoint param, returns breakdown for all partitions."""
    mock_partitions = [
        MagicMock(device="/dev/sda1", mountpoint="/", fstype="ext4"),
    ]

    with (
        patch("psutil.disk_partitions", return_value=mock_partitions),
        patch.object(server, "_get_storage_breakdown", return_value=[
            {"path": "/", "size_bytes": 50000000000, "depth": 0},
            {"path": "/home", "size_bytes": 30000000000, "depth": 1},
            {"path": "/var", "size_bytes": 15000000000, "depth": 1},
        ]),
    ):
        resp = client.get("/api/chatty/health/storage-breakdown", headers=_headers())

    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert "mountpoints" in data
    assert "timestamp" in data
    assert len(data["mountpoints"]) == 1
    assert data["mountpoints"][0] == "/"
    assert data["depth"] == 1
    assert len(data["entries"]) == 3


def test_storage_breakdown_endpoint_with_mountpoint(client):
    """With mountpoint param, returns breakdown for that partition only."""
    with (
        patch.object(server, "_get_storage_breakdown", return_value=[
            {"path": "/mnt/data", "size_bytes": 1000000, "depth": 0},
            {"path": "/mnt/data/photos", "size_bytes": 800000, "depth": 1},
        ]),
    ):
        resp = client.get(
            "/api/chatty/health/storage-breakdown?mountpoint=/mnt/data",
            headers=_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["mountpoints"] == ["/mnt/data"]
    assert len(data["entries"]) == 2
    assert all(e["mountpoint"] == "/mnt/data" for e in data["entries"])


def test_storage_breakdown_endpoint_depth_param(client):
    """depth parameter is passed through to _get_storage_breakdown."""
    with (
        patch.object(server, "_get_storage_breakdown", return_value=[
            {"path": "/", "size_bytes": 100, "depth": 0},
        ]),
        patch("psutil.disk_partitions", return_value=[
            MagicMock(device="/dev/sda1", mountpoint="/", fstype="ext4"),
        ]),
    ):
        resp = client.get("/api/chatty/health/storage-breakdown?depth=2", headers=_headers())

    assert resp.status_code == 200
    assert resp.json()["depth"] == 2


def test_storage_breakdown_skips_snap_partitions(client):
    """Snap squashfs mounts are excluded, same as server_health."""
    mock_partitions = [
        MagicMock(device="/dev/sda1", mountpoint="/", fstype="ext4"),
        MagicMock(device="/dev/loop0", mountpoint="/snap/core/12345", fstype="squashfs"),
    ]

    with (
        patch("psutil.disk_partitions", return_value=mock_partitions),
        patch.object(server, "_get_storage_breakdown", return_value=[
            {"path": "/", "size_bytes": 100, "depth": 0},
        ]),
    ):
        resp = client.get("/api/chatty/health/storage-breakdown", headers=_headers())

    assert resp.status_code == 200
    data = resp.json()
    assert data["mountpoints"] == ["/"]
    assert "/snap/core/12345" not in data["mountpoints"]
