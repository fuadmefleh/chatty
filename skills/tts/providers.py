"""TTS provider integrations: a local engine already running on this
machine, ElevenLabs, and OpenAI.

Each synthesize_* function returns raw MP3 bytes or raises on failure -
skills/tts/tools.py is the single error boundary that turns these into a
structured JSON string for the LLM.
"""
import asyncio
from typing import Optional

import aiohttp
from openai import AsyncOpenAI

from src.core import config

_LOCAL_POLL_INTERVAL_SECONDS = 1.0
_LOCAL_POLL_MAX_ATTEMPTS = 60  # ~60s worst case, matching tts_engine_api's own client timeouts

_ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"


async def synthesize_local(
    text: str, *, engine: Optional[str] = None, voice: Optional[str] = None, speed: int = 100
) -> bytes:
    """Generate speech via the tts_engine_api microservice already running on
    this host: POST /generate -> poll GET /status/{job_id} -> GET
    /download/{filename}. Mirrors the flow used in production by the
    separate tts-for-you project's backend/app/tts_service.py."""
    base_url = config.TTS_LOCAL_ENGINE_URL.rstrip("/")
    payload = {
        "text": text,
        "engine": engine or config.TTS_LOCAL_ENGINE_ENGINE,
        "voice": voice or config.TTS_LOCAL_ENGINE_VOICE,
        "speed": speed,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/generate", json=payload, timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"tts_engine_api /generate failed ({resp.status}): {await resp.text()}")
            data = await resp.json()
        job_id = data["job_id"]

        filename = None
        for _ in range(_LOCAL_POLL_MAX_ATTEMPTS):
            async with session.get(
                f"{base_url}/status/{job_id}", timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"tts_engine_api /status failed ({resp.status}): {await resp.text()}")
                status_data = await resp.json()
            status = status_data.get("status")
            if status == "completed":
                filename = status_data["filename"]
                break
            if status == "failed":
                raise RuntimeError(f"tts_engine_api job failed: {status_data.get('error')}")
            await asyncio.sleep(_LOCAL_POLL_INTERVAL_SECONDS)
        else:
            raise RuntimeError(f"tts_engine_api job {job_id} did not complete in time")

        async with session.get(
            f"{base_url}/download/{filename}", timeout=aiohttp.ClientTimeout(total=120)
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"tts_engine_api /download failed ({resp.status}): {await resp.text()}")
            return await resp.read()


async def synthesize_elevenlabs(
    text: str, *, voice_id: Optional[str] = None, model_id: Optional[str] = None
) -> bytes:
    """Generate speech via the ElevenLabs API. Unlike the local engine, this
    is synchronous - the response body is the raw MP3 directly."""
    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is not configured")

    voice_id = voice_id or config.ELEVENLABS_VOICE_ID
    payload = {
        "text": text,
        "model_id": model_id or config.ELEVENLABS_MODEL_ID,
    }
    headers = {"xi-api-key": config.ELEVENLABS_API_KEY, "Accept": "audio/mpeg"}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{_ELEVENLABS_BASE_URL}/{voice_id}",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"ElevenLabs API failed ({resp.status}): {await resp.text()}")
            return await resp.read()


async def synthesize_openai(text: str, *, model: Optional[str] = None, voice: Optional[str] = None) -> bytes:
    """Generate speech via OpenAI's audio.speech API."""
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    response = await client.audio.speech.create(
        input=text,
        model=model or config.OPENAI_TTS_MODEL,
        voice=voice or config.OPENAI_TTS_VOICE,
        response_format="mp3",
    )
    return await response.read()


_VALID_PROVIDERS = ("local", "elevenlabs", "openai")


async def synthesize(text: str, provider: Optional[str] = None, **kwargs) -> bytes:
    """Dispatch to the configured (or explicitly requested) TTS provider.

    Looks up synthesize_local/synthesize_elevenlabs/synthesize_openai by name
    at call time (rather than a dict built at import time) so callers can
    monkeypatch/override those module-level functions directly.
    """
    provider = provider or config.TTS_PROVIDER
    if provider == "local":
        return await synthesize_local(text, **kwargs)
    if provider == "elevenlabs":
        return await synthesize_elevenlabs(text, **kwargs)
    if provider == "openai":
        return await synthesize_openai(text, **kwargs)
    raise ValueError(f"Unknown TTS provider: {provider!r}. Valid options: {list(_VALID_PROVIDERS)}")
