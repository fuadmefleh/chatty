"""Tests for HeartbeatManager._process_webcam_health_check - the periodic
recheck of saved webcam sources' playability."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers.heartbeat_manager import HeartbeatManager
from src.managers.webcam_manager import WebcamSourcesManager
from src.managers.webcam_verifier import VerifyResult


@pytest.fixture
def hb():
    return HeartbeatManager(skills_manager=MagicMock())


def make_sources_manager(tmp_path):
    return WebcamSourcesManager(data_dir=str(tmp_path / "webcam_sources"))


@pytest.mark.asyncio
async def test_health_check_flags_newly_broken_source_and_leaves_it_enabled(hb, tmp_path):
    mgr = make_sources_manager(tmp_path)
    ok_source = mgr.create(name="Still Fine", url="https://fine.example/cam.jpg", kind="snapshot",
                            verify_status="ok")
    broken_source = mgr.create(name="Went Down", url="https://down.example/cam.jpg", kind="snapshot",
                                verify_status="ok")
    disabled_source = mgr.create(name="Disabled Cam", url="https://disabled.example/cam.jpg", kind="snapshot",
                                  enabled=False, verify_status="ok")

    async def fake_verify(url, kind, client=None):
        if url == broken_source.url:
            return VerifyResult(ok=False, status="unreachable", detail="404")
        return VerifyResult(ok=True, status="ok", detail="fine")

    with patch("src.managers.heartbeat_manager.HeartbeatManager._load_webcam_health_state", return_value={}), \
         patch("src.managers.heartbeat_manager.HeartbeatManager._save_webcam_health_state"), \
         patch("src.managers.webcam_manager.WebcamSourcesManager", return_value=mgr), \
         patch("src.managers.webcam_verifier.verify_webcam", new=AsyncMock(side_effect=fake_verify)):
        summary = await hb._process_webcam_health_check()

    assert summary is not None
    assert "1/2" in summary  # only the 2 enabled sources are checked
    assert "Went Down" in summary

    assert mgr.get(ok_source.id).verify_status == "ok"
    assert mgr.get(broken_source.id).verify_status == "broken"
    assert mgr.get(broken_source.id).enabled is True  # never auto-disabled
    assert mgr.get(disabled_source.id).verify_status == "ok"  # disabled sources aren't rechecked


@pytest.mark.asyncio
async def test_health_check_returns_none_when_everything_ok(hb, tmp_path):
    mgr = make_sources_manager(tmp_path)
    mgr.create(name="Fine", url="https://fine.example/cam.jpg", kind="snapshot", verify_status="ok")

    with patch("src.managers.heartbeat_manager.HeartbeatManager._load_webcam_health_state", return_value={}), \
         patch("src.managers.heartbeat_manager.HeartbeatManager._save_webcam_health_state"), \
         patch("src.managers.webcam_manager.WebcamSourcesManager", return_value=mgr), \
         patch("src.managers.webcam_verifier.verify_webcam", new=AsyncMock(
             return_value=VerifyResult(ok=True, status="ok", detail="fine"))):
        summary = await hb._process_webcam_health_check()

    assert summary is None


@pytest.mark.asyncio
async def test_health_check_skipped_within_interval(hb, tmp_path):
    from datetime import datetime
    mgr = make_sources_manager(tmp_path)
    mgr.create(name="Fine", url="https://fine.example/cam.jpg", kind="snapshot", verify_status="ok")

    with patch("src.managers.heartbeat_manager.HeartbeatManager._load_webcam_health_state",
               return_value={"last_run_at": datetime.now().isoformat()}), \
         patch("src.managers.webcam_manager.WebcamSourcesManager", return_value=mgr) as mock_mgr_cls:
        summary = await hb._process_webcam_health_check()

    assert summary is None
    mock_mgr_cls.assert_not_called()


@pytest.mark.asyncio
async def test_health_check_no_enabled_sources_returns_none(hb, tmp_path):
    mgr = make_sources_manager(tmp_path)

    with patch("src.managers.heartbeat_manager.HeartbeatManager._load_webcam_health_state", return_value={}), \
         patch("src.managers.heartbeat_manager.HeartbeatManager._save_webcam_health_state"), \
         patch("src.managers.webcam_manager.WebcamSourcesManager", return_value=mgr):
        summary = await hb._process_webcam_health_check()

    assert summary is None
