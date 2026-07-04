"""Tests for HeartbeatManager._process_transcription_mining."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers.heartbeat_manager import HeartbeatManager


def make_manager():
    return HeartbeatManager(skills_manager=MagicMock())


def make_transcription(t_id: str, content: str, created_at: str = "2026-01-01T08:00:00"):
    t = MagicMock()
    t.id = t_id
    t.content = content
    t.created_at = created_at
    return t


@pytest.mark.asyncio
async def test_no_web_user_id_short_circuits():
    hb = make_manager()

    with patch("src.core.config.WEB_USER_ID", ""):
        result = await hb._process_transcription_mining()

    assert result is None


@pytest.mark.asyncio
async def test_no_pending_transcriptions_returns_none():
    hb = make_manager()

    transcriptions_mgr = MagicMock()
    transcriptions_mgr.get_pending.return_value = []

    with patch("src.core.config.WEB_USER_ID", "web_user"), \
         patch("skills.transcriptions.transcriptions_manager.TranscriptionsManager", return_value=transcriptions_mgr):

        result = await hb._process_transcription_mining()

    assert result is None
    transcriptions_mgr.archive.assert_not_called()


@pytest.mark.asyncio
async def test_pending_transcriptions_are_mined_and_archived():
    hb = make_manager()

    pending = [make_transcription("t1", "met with Sam about the rocket project")]
    transcriptions_mgr = MagicMock()
    transcriptions_mgr.get_pending.return_value = pending

    memory_manager = MagicMock()
    memory_manager.consolidate_text = AsyncMock(return_value="Extracted and stored long-term memory from text.")

    with patch("src.core.config.WEB_USER_ID", "web_user"), \
         patch("skills.transcriptions.transcriptions_manager.TranscriptionsManager", return_value=transcriptions_mgr), \
         patch("src.core.memory.MemoryManager", return_value=memory_manager):

        result = await hb._process_transcription_mining()

    memory_manager.consolidate_text.assert_awaited_once()
    mined_text = memory_manager.consolidate_text.await_args.args[0]
    assert "met with Sam about the rocket project" in mined_text

    transcriptions_mgr.archive.assert_called_once_with("web_user", ["t1"])
    assert result is not None and "1 into long-term memory" in result


@pytest.mark.asyncio
async def test_error_during_mining_does_not_raise():
    hb = make_manager()

    transcriptions_mgr = MagicMock()
    transcriptions_mgr.get_pending.side_effect = RuntimeError("disk error")

    with patch("src.core.config.WEB_USER_ID", "web_user"), \
         patch("skills.transcriptions.transcriptions_manager.TranscriptionsManager", return_value=transcriptions_mgr):

        result = await hb._process_transcription_mining()

    assert result is None
