"""Telegram message utilities for safe sending of potentially long messages.

Telegram imposes a 4096-character limit per message. This module provides
utilities to split long strings into valid chunks and send them reliably,
with word-boundary preservation and per-chunk error handling.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Telegram's hard limit is 4096 characters. We use 4000 to leave a safety
# margin for markdown/entities and to keep chunks comfortably under the cap.
MAX_TELEGRAM_MESSAGE_LENGTH = 4000


def split_for_telegram(text: str, max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> list[str]:
    """Split *text* into chunks that fit inside Telegram's message limit.

    Splits preserve word boundaries so that no chunk ends mid-word.
    If a single word is longer than *max_length*, the word is split
    anyway (worst-case fallback).

    Args:
        text: The full message text.
        max_length: Maximum characters per chunk (default 4000).

    Returns:
        A list of strings, each at most *max_length* characters long.
    """
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Start with the first max_length characters
        cut = remaining[:max_length]
        # Find the last whitespace within the cut to avoid mid-word splits
        last_space = cut.rfind(" ")
        if last_space > max_length // 2:
            # Split at the last space (must be > half to avoid tiny fragments)
            chunks.append(cut[:last_space])
            remaining = remaining[last_space:].lstrip()
        else:
            # No good split point; force-split at max_length
            chunks.append(cut)
            remaining = remaining[max_length:]

    return chunks


async def safe_send_reply(
    message_obj: Any,
    text: str,
    *,
    delay: float = 0.5,
    **kwargs: Any,
) -> list:
    """Send *text* via ``message_obj.reply_text()``, splitting if needed.

    Wraps each individual send in a try/except so that one chunk failing
    does not prevent the remaining chunks from being sent.

    Args:
        message_obj: Telegram ``Message`` (or compatible) with a
            ``reply_text`` coroutine method.
        text: The full message text to send.
        delay: Seconds to wait between chunks (default 0.5).
        **kwargs: Extra keyword arguments forwarded to ``reply_text``
            (e.g. ``parse_mode``).

    Returns:
        A list of successfully sent ``Message`` objects.
    """
    chunks = split_for_telegram(text)
    sent: list = []

    for idx, chunk in enumerate(chunks):
        try:
            msg = await message_obj.reply_text(chunk, **kwargs)
            sent.append(msg)
            if idx < len(chunks) - 1:
                await asyncio.sleep(delay)
        except Exception as exc:
            logger.error(
                "Failed to send reply chunk %d/%d (%d chars): %s",
                idx + 1,
                len(chunks),
                len(chunk),
                exc,
            )

    return sent


async def safe_send_message(
    bot: Any,
    chat_id: str | int,
    text: str,
    *,
    delay: float = 0.5,
    **kwargs: Any,
) -> list:
    """Send *text* via ``bot.send_message()``, splitting if needed.

    Wraps each individual send in a try/except so that one chunk failing
    does not prevent the remaining chunks from being sent.

    Args:
        bot: Telegram ``Bot`` instance with a ``send_message`` coroutine.
        chat_id: Target chat ID.
        text: The full message text to send.
        delay: Seconds to wait between chunks (default 0.5).
        **kwargs: Extra keyword arguments forwarded to ``send_message``.

    Returns:
        A list of successfully sent ``Message`` objects.
    """
    chunks = split_for_telegram(text)
    sent: list = []

    for idx, chunk in enumerate(chunks):
        try:
            msg = await bot.send_message(chat_id=chat_id, text=chunk, **kwargs)
            sent.append(msg)
            if idx < len(chunks) - 1:
                await asyncio.sleep(delay)
        except Exception as exc:
            logger.error(
                "Failed to send message chunk %d/%d (%d chars): %s",
                idx + 1,
                len(chunks),
                len(chunk),
                exc,
            )

    return sent
