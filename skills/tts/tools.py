"""Text-to-speech skill tools for LLM function calling."""
import asyncio
import importlib.util
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from telegram import Bot

from src.core import config
from src.core.request_context import current_chat_id
from src.core.skill_tool import SkillTool

# Load the providers module from this skill folder
_providers_path = Path(__file__).parent / "providers.py"
_spec = importlib.util.spec_from_file_location("tts_providers", _providers_path)
_providers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_providers)

_FFMPEG_TIMEOUT_SECONDS = 30


async def _transcode_to_ogg_opus(mp3_bytes: bytes) -> Optional[bytes]:
    """Transcode MP3 bytes to OGG/Opus via ffmpeg so Telegram accepts it as a
    native voice bubble (bot.send_voice requires OGG/Opus). Returns None if
    ffmpeg is unavailable or fails, so the caller can fall back to send_audio
    with the raw MP3 instead."""
    in_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    out_path = in_file.name + ".ogg"
    try:
        in_file.write(mp3_bytes)
        in_file.close()

        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-v", "error",
            "-i", in_file.name,
            "-c:a", "libopus", "-b:a", "64k", "-f", "ogg", out_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=_FFMPEG_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            proc.kill()
            logging.error("ffmpeg transcode to ogg/opus timed out")
            return None

        if proc.returncode != 0 or not os.path.exists(out_path):
            logging.error(f"ffmpeg transcode to ogg/opus failed: {stderr.decode('utf-8', errors='replace')}")
            return None

        return Path(out_path).read_bytes()
    except FileNotFoundError:
        logging.error("ffmpeg is not installed - falling back to sending raw audio")
        return None
    finally:
        for path in (in_file.name, out_path):
            try:
                os.unlink(path)
            except OSError:
                pass


class SpeakTextTool(SkillTool):
    """Speak text back to the user as a real Telegram voice message."""

    name = "speak_text"
    description = (
        "Speak the given text back to the user as a real Telegram voice message, "
        "using a local TTS engine, ElevenLabs, or OpenAI. Use this only when the "
        "user explicitly asks to hear something spoken/said out loud or asks for "
        "a voice message - not for normal text replies. Only works in the "
        "Telegram bot, not the web dashboard chat."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to speak.",
            },
            "provider": {
                "type": "string",
                "enum": ["local", "elevenlabs", "openai"],
                "description": (
                    "Which TTS backend to use. Defaults to the configured TTS_PROVIDER "
                    "if not specified."
                ),
            },
        },
        "required": ["text"],
    }

    async def execute(self, text: str, provider: Optional[str] = None) -> str:
        chat_id = current_chat_id.get()
        if chat_id is None:
            return json.dumps({
                "success": False,
                "error": "No active Telegram chat to send a voice message to.",
            })

        try:
            mp3_bytes = await _providers.synthesize(text, provider=provider)
        except Exception as e:
            return json.dumps({"success": False, "error": f"TTS synthesis failed: {e}"})

        ogg_bytes = await _transcode_to_ogg_opus(mp3_bytes)

        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        try:
            if ogg_bytes is not None:
                await bot.send_voice(chat_id=chat_id, voice=ogg_bytes)
            else:
                await bot.send_audio(chat_id=chat_id, audio=mp3_bytes, filename="speech.mp3")
        except Exception as e:
            return json.dumps({"success": False, "error": f"Failed to send voice message: {e}"})

        return json.dumps({"success": True, "message": "Voice message sent."})
