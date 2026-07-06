"""OpenMontage video generation API wrapper.

Submits a text prompt to OpenMontage's agent pipeline, polls for completion,
downloads the result, and saves it to the chat uploads directory so the web
server can serve it (same /api/chatty/chat-media/ path used by image
generation).
"""
import asyncio
import os
import uuid
from pathlib import Path
from typing import Optional

import aiohttp

from src.core import config

_DEFAULT_POLL_INTERVAL_SECONDS = 3
_DEFAULT_POLL_MAX_ATTEMPTS = 120  # up to 6 minutes at 3s intervals
_VALID_DURATIONS = {2, 4, 6, 8, 10, 15}
_VALID_RESOLUTIONS = {"480p", "720p", "1080p", "auto"}

# Override in tests or config
_POLL_INTERVAL = _DEFAULT_POLL_INTERVAL_SECONDS
_POLL_MAX_ATTEMPTS = _DEFAULT_POLL_MAX_ATTEMPTS


def _chat_uploads_dir() -> Path:
    """Same uploads/chat directory chatty_web_server.py's _chat_uploads_dir()
    writes to and serves from - duplicated here to avoid a circular import
    (same reasoning as config.WEB_USER_ID's own docstring)."""
    d = config.MEMORY_DIR / config.WEB_USER_ID / "uploads" / "chat"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def generate_video(
    prompt: str,
    *,
    duration_seconds: Optional[int] = None,
    resolution: str = "auto",
) -> dict:
    """Submit a video generation job to OpenMontage and wait for it to complete.

    Args:
        prompt: Text description of the desired video.
        duration_seconds: Length of the video in seconds (2-15). Defaults to 4.
        resolution: Output resolution ("480p", "720p", "1080p", or "auto").

    Returns:
        Dict with ``success`` bool and either ``url`` (on success) or ``error``
        string (on failure).
    """
    api_key = config.OPENMONTAGE_API_KEY
    if not api_key:
        return {
            "success": False,
            "error": "OPENMONTAGE_API_KEY is not configured",
        }

    base_url = config.OPENMONTAGE_API_URL.rstrip("/")
    duration_seconds = duration_seconds or 4
    if duration_seconds not in _VALID_DURATIONS:
        # clamp to nearest valid value
        duration_seconds = min(_VALID_DURATIONS, key=lambda x: abs(x - duration_seconds))
    if resolution not in _VALID_RESOLUTIONS:
        resolution = "auto"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "duration_seconds": duration_seconds,
        "resolution": resolution,
    }

    async with aiohttp.ClientSession() as session:
        # Submit the generation job
        async with session.post(
            f"{base_url}/v1/generate",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 202:
                error_text = await resp.text()
                return {
                    "success": False,
                    "error": f"OpenMontage job submission failed ({resp.status}): {error_text}",
                }
            job_data = await resp.json()
            job_id = job_data.get("job_id")
            if not job_id:
                return {
                    "success": False,
                    "error": "OpenMontage response missing job_id",
                }

        # Poll for completion
        video_url = await _poll_job(session, f"{base_url}/v1/jobs/{job_id}", headers)
        if video_url is None:
            return {"success": False, "error": "Video generation timed out"}

        # Download the video
        async with session.get(
            f"{base_url}/v1/jobs/{job_id}/download",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=300),
        ) as resp:
            if resp.status != 200:
                return {
                    "success": False,
                    "error": f"Video download failed ({resp.status}): {await resp.text()}",
                }
            video_bytes = await resp.read()

    # Save to uploads dir
    filename = f"{uuid.uuid4()}.mp4"
    await asyncio.to_thread((_chat_uploads_dir() / filename).write_bytes, video_bytes)

    # Build the service URL (same auth path as chat-media endpoint)
    api_key_param = os.getenv("CHATTY_WEB_API_KEY", "changeme")
    url = f"/api/chatty/chat-media/{filename}?api_key={api_key_param}"

    return {
        "success": True,
        "url": url,
        "duration_seconds": duration_seconds,
        "resolution": resolution,
    }


async def _poll_job(session, status_url: str, headers: dict) -> Optional[str]:
    """Poll the OpenMontage job status endpoint until the video is ready.

    Returns the download URL on success, or None on timeout.
    """
    for _ in range(_POLL_MAX_ATTEMPTS):
        async with session.get(
            status_url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()

        status = data.get("status")
        if status == "completed":
            return data.get("download_url")
        if status in ("failed", "cancelled"):
            raise RuntimeError(
                f"OpenMontage job {status}: {data.get('error', 'no details')}"
            )

        await asyncio.sleep(_POLL_INTERVAL)

    return None
