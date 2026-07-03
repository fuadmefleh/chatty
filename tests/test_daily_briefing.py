"""Tests for HeartbeatManager._process_daily_briefing (hour + once-per-day gating)."""
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers.heartbeat_manager import HeartbeatManager


def make_manager():
    hb = HeartbeatManager(skills_manager=MagicMock())
    hb._send_message_callback = AsyncMock()
    return hb


@pytest.mark.asyncio
async def test_skips_when_not_the_briefing_hour():
    hb = make_manager()

    class FakeNow(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 1, 1, 14, 0, 0)  # 2pm

    with patch("src.managers.heartbeat_manager.datetime", FakeNow), \
         patch("src.main.authorized_users", {"u1": "phone"}), \
         patch("src.core.config.DAILY_BRIEFING_HOUR", 8):
        result = await hb._process_daily_briefing()

    assert result is None
    hb._send_message_callback.assert_not_awaited()


@pytest.mark.asyncio
async def test_sends_once_at_the_briefing_hour_and_not_again_same_day():
    hb = make_manager()
    hb._build_daily_briefing_sections = AsyncMock(return_value=["Nothing notable to report today."])

    class FakeNow(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 1, 1, 8, 5, 0)  # 8:05am, briefing hour

    with tempfile.TemporaryDirectory() as tmp_dir:
        state_path = Path(tmp_dir) / "data" / "daily_briefing_state.json"

        with patch("src.managers.heartbeat_manager.datetime", FakeNow), \
             patch("src.main.authorized_users", {"u1": "phone"}), \
             patch("src.core.config.DAILY_BRIEFING_HOUR", 8), \
             patch("src.core.config.BASE_DIR", Path(tmp_dir)):

            first_result = await hb._process_daily_briefing()
            assert first_result is not None and "1 user" in first_result
            hb._send_message_callback.assert_awaited_once()
            assert state_path.exists()
            assert json.loads(state_path.read_text()) == {"u1": "2026-01-01"}

            # A second tick the same hour/day should not send again.
            hb._send_message_callback.reset_mock()
            second_result = await hb._process_daily_briefing()
            assert second_result is None
            hb._send_message_callback.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_authorized_users_short_circuits():
    hb = make_manager()

    with patch("src.main.authorized_users", {}):
        result = await hb._process_daily_briefing()

    assert result is None
    hb._send_message_callback.assert_not_awaited()
