"""Tests for HeartbeatManager._process_self_upgrade_ideas (interval gating +
delegation to src/managers/self_upgrade_manager.py)."""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers.heartbeat_manager import HeartbeatManager


def make_manager():
    hb = HeartbeatManager(skills_manager=MagicMock())
    hb._send_message_callback = AsyncMock()
    return hb


@pytest.mark.asyncio
async def test_no_authorized_users_short_circuits():
    hb = make_manager()

    with patch("src.main.authorized_users", {}):
        result = await hb._process_self_upgrade_ideas()

    assert result is None


@pytest.mark.asyncio
async def test_within_interval_is_skipped():
    hb = make_manager()

    with tempfile_state({"last_run_at": datetime.now().isoformat()}) as _, \
         patch("src.main.authorized_users", {"u1": "phone"}), \
         patch("src.core.config.SELF_UPGRADE_INTERVAL_HOURS", 168):
        result = await hb._process_self_upgrade_ideas()

    assert result is None


@pytest.mark.asyncio
async def test_past_interval_generates_and_delegates():
    hb = make_manager()

    with tempfile_state({"last_run_at": (datetime.now() - timedelta(hours=200)).isoformat()}) as _, \
         patch("src.main.authorized_users", {"u1": "phone"}), \
         patch("src.core.config.SELF_UPGRADE_INTERVAL_HOURS", 168), \
         patch("src.managers.self_upgrade_manager.generate_self_upgrade_idea", new_callable=AsyncMock) as mock_gen, \
         patch("src.managers.self_upgrade_manager.run_self_upgrade", new_callable=AsyncMock) as mock_run, \
         patch("skills.pi_agent.requests_manager.FeatureRequestsManager"):

        mock_gen.return_value = "Add a skill that does X"
        mock_run.return_value = "🔧 Self-upgrade merged: add-a-skill (restarting chatty-bot)"

        result = await hb._process_self_upgrade_ideas()

    mock_gen.assert_awaited_once()
    mock_run.assert_awaited_once()
    assert mock_run.await_args.args[0] == "Add a skill that does X"
    assert result is not None and "merged" in result.lower()


@pytest.mark.asyncio
async def test_no_idea_generated_is_a_quiet_noop():
    hb = make_manager()

    with tempfile_state({}) as _, \
         patch("src.main.authorized_users", {"u1": "phone"}), \
         patch("src.core.config.SELF_UPGRADE_INTERVAL_HOURS", 168), \
         patch("src.managers.self_upgrade_manager.generate_self_upgrade_idea", new_callable=AsyncMock) as mock_gen, \
         patch("src.managers.self_upgrade_manager.run_self_upgrade", new_callable=AsyncMock) as mock_run, \
         patch("skills.pi_agent.requests_manager.FeatureRequestsManager"):

        mock_gen.return_value = None

        result = await hb._process_self_upgrade_ideas()

    mock_gen.assert_awaited_once()
    mock_run.assert_not_awaited()
    assert result is None


class tempfile_state:
    """Context manager that patches the self-upgrade state file to a temp dir
    pre-seeded with `initial_state`, so tests don't touch real data/ files."""

    def __init__(self, initial_state: dict):
        self.initial_state = initial_state
        self._tmpdir_ctx = None
        self._patch = None

    def __enter__(self):
        import tempfile
        import json
        self._tmpdir_ctx = tempfile.TemporaryDirectory()
        tmp_dir = Path(self._tmpdir_ctx.name)
        if self.initial_state:
            (tmp_dir / "data").mkdir(parents=True, exist_ok=True)
            (tmp_dir / "data" / "self_upgrade_state.json").write_text(json.dumps(self.initial_state))
        self._patch = patch("src.core.config.BASE_DIR", tmp_dir)
        self._patch.start()
        return tmp_dir

    def __exit__(self, *exc):
        self._patch.stop()
        self._tmpdir_ctx.cleanup()
