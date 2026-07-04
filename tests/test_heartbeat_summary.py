"""Tests for HeartbeatManager._send_heartbeat_summary.

Deliberately does NOT call execute_heartbeat() directly: that method calls
through to _process_world_watch/_process_memory_watch_suggestions/
_process_daily_briefing/_process_self_upgrade_ideas (real network/LLM calls,
and - since this repo's data/authorized_users.json has a real entry - even a
real self-upgrade attempt) plus a real agent.think() LLM call at the end.
Those are covered in isolation with proper mocking in test_world_watch.py,
test_daily_briefing.py, test_memory_suggestions.py, and
test_heartbeat_self_upgrade.py. This file only exercises the summary
formatting/sending logic itself.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers.heartbeat_manager import HeartbeatManager


def make_manager():
    return HeartbeatManager(skills_manager=MagicMock())


@pytest.mark.asyncio
async def test_summary_sent_to_all_authorized_users():
    hb = make_manager()
    send = AsyncMock()
    hb.set_send_message_callback(send)

    with patch("src.main.authorized_users", {"user1": "phone1", "user2": "phone2"}):
        await hb._send_heartbeat_summary(["📧 Gmail: inbox clean"], "2026-01-01 08:00 AM")

    assert send.await_count == 2
    sent_user_ids = {call.args[0] for call in send.await_args_list}
    assert sent_user_ids == {"user1", "user2"}
    message = send.await_args_list[0].args[1]
    assert "Heartbeat Summary" in message
    assert "📧 Gmail: inbox clean" in message
    assert "2026-01-01 08:00 AM" in message


@pytest.mark.asyncio
async def test_empty_summary_sends_nothing():
    hb = make_manager()
    send = AsyncMock()
    hb.set_send_message_callback(send)

    with patch("src.main.authorized_users", {"user1": "phone1"}):
        await hb._send_heartbeat_summary([], "2026-01-01 08:00 AM")

    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_callback_configured_does_not_raise():
    hb = make_manager()  # no send_message_callback set

    with patch("src.main.authorized_users", {"user1": "phone1"}):
        await hb._send_heartbeat_summary(["something happened"], "2026-01-01 08:00 AM")
    # No exception is the assertion here.


@pytest.mark.asyncio
async def test_no_authorized_users_sends_nothing():
    hb = make_manager()
    send = AsyncMock()
    hb.set_send_message_callback(send)

    with patch("src.main.authorized_users", {}):
        await hb._send_heartbeat_summary(["something happened"], "2026-01-01 08:00 AM")

    send.assert_not_awaited()
