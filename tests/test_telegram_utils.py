#!/usr/bin/env python3
"""Unit tests for src.core.telegram_utils (split_for_telegram, safe_send_reply, safe_send_message)."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add parent directory to path so we can import src.*
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.telegram_utils import split_for_telegram, MAX_TELEGRAM_MESSAGE_LENGTH


# ---------------------------------------------------------------------------
# split_for_telegram
# ---------------------------------------------------------------------------

def test_short_string_returns_single_chunk():
    """Strings below the limit are returned as-is."""
    text = "Hello world"
    assert split_for_telegram(text) == [text]


def test_exactly_at_limit_returns_single_chunk():
    """A string exactly at max_length is not split."""
    text = "A" * MAX_TELEGRAM_MESSAGE_LENGTH
    assert split_for_telegram(text) == [text]


def test_just_over_limit_splits_at_last_word_boundary():
    """One character over the limit should produce two chunks."""
    # Build a string of words separated by spaces that is slightly over the limit
    word = "word " * 800  # ~4000 chars
    # Pad to exceed the limit slightly
    text = word + "extra"
    chunks = split_for_telegram(text)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= MAX_TELEGRAM_MESSAGE_LENGTH, f"chunk too long: {len(c)}"
    # Verify all non-space characters are preserved (spaces at split boundaries are consumed)
    text_no_spaces = text.replace(" ", "")
    rejoined_no_spaces = "".join(chunks).replace(" ", "")
    assert text_no_spaces == rejoined_no_spaces, "non-space content mismatch"


def test_very_long_string_produces_multiple_chunks():
    """A 15000-character string should produce ~4 chunks."""
    text = "test " * 3000  # 15000 chars
    chunks = split_for_telegram(text)
    assert len(chunks) >= 3
    for c in chunks:
        assert len(c) <= MAX_TELEGRAM_MESSAGE_LENGTH, f"chunk too long: {len(c)}"


def test_word_boundary_preservation():
    """No chunk should end in the middle of a word."""
    words = ["alpha", "beta", "gamma", "delta", "epsilon",
             "zeta", "eta", "theta", "iota", "kappa"] * 200  # 2000 words
    text = " ".join(words)
    chunks = split_for_telegram(text)

    for chunk in chunks:
        stripped = chunk.rstrip()
        # The last character before trailing spaces should not be part of a
        # split word (i.e., the word should be complete).
        last_word = stripped.split()[-1] if stripped.split() else ""
        assert " " not in last_word, f"chunk ends mid-word: ...{last_word}"


def test_long_word_split_fallback():
    """If a single word is longer than max_length, it is still split."""
    giant_word = "x" * (MAX_TELEGRAM_MESSAGE_LENGTH + 100)
    text = f"prefix {giant_word} suffix"
    chunks = split_for_telegram(text)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= MAX_TELEGRAM_MESSAGE_LENGTH


def test_custom_max_length():
    """Passing a smaller max_length should produce more chunks."""
    text = "word " * 1000  # 5000 chars
    chunks_default = split_for_telegram(text, max_length=4000)
    chunks_small = split_for_telegram(text, max_length=1000)
    assert len(chunks_small) > len(chunks_default)
    for c in chunks_small:
        assert len(c) <= 1000


def test_empty_string():
    """Empty string returns a single empty chunk."""
    assert split_for_telegram("") == [""]


def test_content_integrity_across_chunks():
    """All content from the original string is preserved in chunks."""
    # Use unique markers at known positions
    marker_positions = [100, 2000, 3999, 4001, 8000, 12000]
    parts = []
    last = 0
    for pos in sorted(marker_positions):
        parts.append("a" * (pos - last))
        parts.append(f"MARKER_{pos}")
        last = pos + len(f"MARKER_{pos}")
    parts.append("b" * (15000 - last + len(parts[-1])))
    text = "".join(parts)

    chunks = split_for_telegram(text)
    rejoined = "".join(chunks)

    for pos in marker_positions:
        marker = f"MARKER_{pos}"
        assert marker in rejoined, f"{marker} lost in splitting"


# ---------------------------------------------------------------------------
# safe_send_reply (smoke test)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_safe_send_reply_short_message():
    """Short message: one reply_text call, no delay."""
    from src.core.telegram_utils import safe_send_reply

    msg = MagicMock()
    msg.reply_text = AsyncMock(return_value=MagicMock())

    result = await safe_send_reply(msg, "Hello", delay=0.01)
    assert len(result) == 1
    msg.reply_text.assert_called_once_with("Hello")


@pytest.mark.asyncio
async def test_safe_send_reply_long_message_splits():
    """Long message: multiple reply_text calls with correct chunks."""
    from src.core.telegram_utils import safe_send_reply

    msg = MagicMock()
    msg.reply_text = AsyncMock(return_value=MagicMock())

    text = "x" * (MAX_TELEGRAM_MESSAGE_LENGTH + 500)
    result = await safe_send_reply(msg, text, delay=0.01)

    expected_chunks = split_for_telegram(text)
    assert len(result) == len(expected_chunks)
    assert msg.reply_text.call_count == len(expected_chunks)
    for call, chunk in zip(msg.reply_text.call_args_list, expected_chunks):
        assert call[0][0] == chunk


@pytest.mark.asyncio
async def test_safe_send_reply_per_chunk_error_handling():
    """If one chunk fails, remaining chunks are still sent."""
    from src.core.telegram_utils import safe_send_reply

    msg = MagicMock()

    call_count = 0
    async def flaky_reply(text, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise Exception("simulated failure")
        return MagicMock()

    msg.reply_text = flaky_reply

    # Produce exactly 3 chunks (3 * 4000 = 12000, plus a bit)
    text = "x" * (MAX_TELEGRAM_MESSAGE_LENGTH * 2 + 100)
    result = await safe_send_reply(msg, text, delay=0.01)

    # 3 chunks produced; chunk 2 fails, so 2 succeeded
    assert len(result) == 2, f"expected 2, got {len(result)}"
    assert call_count == 3


@pytest.mark.asyncio
async def test_safe_send_reply_passes_kwargs():
    """Extra kwargs (e.g. parse_mode) are forwarded to reply_text."""
    from src.core.telegram_utils import safe_send_reply

    msg = MagicMock()
    msg.reply_text = AsyncMock(return_value=MagicMock())

    await safe_send_reply(msg, "*bold*", parse_mode="MarkdownV2")
    msg.reply_text.assert_called_once_with("*bold*", parse_mode="MarkdownV2")


# ---------------------------------------------------------------------------
# safe_send_message (smoke test)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_safe_send_message_long():
    """Bot.send_message is called once per chunk."""
    from src.core.telegram_utils import safe_send_message

    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock())

    text = "x" * (MAX_TELEGRAM_MESSAGE_LENGTH + 500)
    result = await safe_send_message(bot, chat_id="12345", text=text, delay=0.01)

    expected_chunks = split_for_telegram(text)
    assert len(result) == len(expected_chunks)
    assert bot.send_message.call_count == len(expected_chunks)
    for call in bot.send_message.call_args_list:
        assert call[1]["chat_id"] == "12345"


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_tests():
    """Run all tests and print results."""
    import traceback

    # Sync tests
    sync_tests = [
        ("short string -> single chunk", test_short_string_returns_single_chunk),
        ("exactly at limit -> single chunk", test_exactly_at_limit_returns_single_chunk),
        ("just over limit splits at word boundary", test_just_over_limit_splits_at_last_word_boundary),
        ("very long string -> multiple chunks", test_very_long_string_produces_multiple_chunks),
        ("word boundary preservation", test_word_boundary_preservation),
        ("long word split fallback", test_long_word_split_fallback),
        ("custom max_length", test_custom_max_length),
        ("empty string", test_empty_string),
        ("content integrity across chunks", test_content_integrity_across_chunks),
    ]

    # Async tests
    async_tests = [
        ("safe_send_reply short", test_safe_send_reply_short_message),
        ("safe_send_reply long splits", test_safe_send_reply_long_message_splits),
        ("safe_send_reply per-chunk error handling", test_safe_send_reply_per_chunk_error_handling),
        ("safe_send_reply passes kwargs", test_safe_send_reply_passes_kwargs),
        ("safe_send_message long", test_safe_send_message_long),
    ]

    passed = 0
    failed = 0

    for name, fn in sync_tests:
        try:
            fn()
            print(f"  ✅ {name}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            traceback.print_exc()
            failed += 1

    for name, fn in async_tests:
        try:
            asyncio.get_event_loop().run_until_complete(fn())
            print(f"  ✅ {name}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    failed = run_tests()
    sys.exit(1 if failed else 0)
