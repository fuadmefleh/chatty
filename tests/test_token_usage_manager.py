"""Tests for prompt capture in TokenUsageManager."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.token_usage_manager import (  # noqa: E402
    PROMPT_PREVIEW_LIMIT,
    TokenUsageManager,
    summarize_last_message,
)


@pytest.fixture
def manager(tmp_path):
    return TokenUsageManager(db_path=str(tmp_path / "token_usage.db"))


# ── summarize_last_message ────────────────────────────────────────────────

def test_plain_string_content():
    assert summarize_last_message([{"role": "user", "content": "hello"}]) == ("user", "hello")


def test_uses_last_message_not_last_user_turn():
    messages = [
        {"role": "user", "content": "search my mail"},
        {"role": "assistant", "content": "calling tool"},
        {"role": "tool", "content": '{"results": []}'},
    ]
    assert summarize_last_message(messages) == ("tool", '{"results": []}')


def test_text_blocks_are_joined():
    messages = [{"role": "user", "content": [
        {"type": "text", "text": "first"},
        {"type": "text", "text": "second"},
    ]}]
    assert summarize_last_message(messages) == ("user", "first\nsecond")


def test_image_blocks_become_placeholder_not_base64():
    messages = [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "data": "A" * 5000}},
        {"type": "text", "text": "what is this?"},
    ]}]
    role, text = summarize_last_message(messages)
    assert role == "user"
    assert text == "[image]\nwhat is this?"
    assert "AAAA" not in text


def test_unknown_blocks_fall_back_to_json():
    messages = [{"role": "tool", "content": [{"type": "tool_result", "content": "ok"}]}]
    _, text = summarize_last_message(messages)
    assert '"tool_result"' in text


def test_long_content_is_truncated():
    messages = [{"role": "user", "content": "x" * (PROMPT_PREVIEW_LIMIT + 500)}]
    _, text = summarize_last_message(messages)
    assert text.endswith("… (truncated)")
    assert len(text) == PROMPT_PREVIEW_LIMIT + len("… (truncated)")


def test_content_exactly_at_limit_is_not_truncated():
    messages = [{"role": "user", "content": "x" * PROMPT_PREVIEW_LIMIT}]
    _, text = summarize_last_message(messages)
    assert text == "x" * PROMPT_PREVIEW_LIMIT


@pytest.mark.parametrize("messages", [None, [], [{"role": "user"}], [{"role": "user", "content": ""}]])
def test_missing_or_empty_content_yields_no_preview(messages):
    _, text = summarize_last_message(messages)
    assert text is None


def test_role_defaults_when_absent():
    role, _ = summarize_last_message([{"content": "hi"}])
    assert role == "unknown"


# ── record / get_recent ───────────────────────────────────────────────────

def test_record_round_trips_prompt(manager):
    manager.record("anthropic", "claude-opus-4-8", 100, 20,
                   prompt_role="user", prompt_preview="what's my schedule?")
    entry = manager.get_recent(limit=1)[0]
    assert entry["prompt_role"] == "user"
    assert entry["prompt_preview"] == "what's my schedule?"
    assert entry["total_tokens"] == 120


def test_record_without_prompt_stores_nulls(manager):
    manager.record("openai", "gpt-4o", 10, 5)
    entry = manager.get_recent(limit=1)[0]
    assert entry["prompt_role"] is None
    assert entry["prompt_preview"] is None


def test_migration_adds_columns_to_preexisting_db(tmp_path):
    """Rows written before prompt capture existed must survive and read back null."""
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_tokens INTEGER NOT NULL,
            completion_tokens INTEGER NOT NULL,
            total_tokens INTEGER NOT NULL
        )
    """)
    conn.execute(
        """INSERT INTO token_usage
           (timestamp, provider, model, prompt_tokens, completion_tokens, total_tokens)
           VALUES ('2026-07-01T00:00:00+00:00', 'openai', 'gpt-4o', 7, 3, 10)"""
    )
    conn.commit()
    conn.close()

    mgr = TokenUsageManager(db_path=str(db_path))
    entries = mgr.get_recent(limit=10)
    assert len(entries) == 1
    assert entries[0]["total_tokens"] == 10
    assert entries[0]["prompt_preview"] is None

    mgr.record("anthropic", "claude-opus-4-8", 1, 1, prompt_role="user", prompt_preview="new")
    assert mgr.get_recent(limit=1)[0]["prompt_preview"] == "new"


def test_summary_still_works_with_prompt_columns(manager):
    manager.record("anthropic", "claude-opus-4-8", 100, 20, prompt_role="user", prompt_preview="hi")
    summary = manager.get_summary(days=30)
    assert summary["request_count"] == 1
    assert summary["total_tokens"] == 120
