"""Webcam verification: given a URL and a claimed `kind` (see WEBCAM_KINDS in
webcam_manager.py), actually fetch it and check whether it looks like a real,
playable live feed of that kind - rather than trusting an LLM's guess or a
manually-typed URL at face value.

Used from three places:
- src/managers/webcam_discovery.py - pre-vet curated suggestions before they
  ever become a pending suggestion on the dashboard.
- src/web/routers/webcam.py - gate manual "add source" / suggestion "approve"
  (both can be overridden with force=True for false negatives).
- src/managers/heartbeat_manager.py's periodic health-check job - re-verify
  already-saved sources so stale/dead links get flagged over time.

Every check is a best-effort heuristic on response status/content-type/body
shape, not a guarantee the feed is watchable right now - it's meant to catch
the common cases (dead link, wrong content-type, non-existent video) cheaply
and quickly, not to fully validate media codecs/playback.
"""
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, quote

import httpx

from src.core import config
from src.core.logging_config import get_heartbeat_logger

logger = get_heartbeat_logger()

_USER_AGENT = "Mozilla/5.0 (compatible; ChattyWebcamVerifier/1.0)"

# youtube.com/watch?v=ID, youtu.be/ID, youtube.com/live/ID, /shorts/ID, /embed/ID
_YOUTUBE_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|live/|shorts/|embed/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{6,})"
)


@dataclass
class VerifyResult:
    ok: bool
    status: str  # "ok" | "unreachable" | "unsupported"
    detail: str


def extract_youtube_id(url: str) -> Optional[str]:
    match = _YOUTUBE_ID_RE.search(url)
    return match.group(1) if match else None


def _new_client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": _USER_AGENT},
    )


async def _verify_snapshot(client: httpx.AsyncClient, url: str) -> VerifyResult:
    resp = await client.get(url)
    if resp.status_code >= 400:
        return VerifyResult(False, "unreachable", f"HTTP {resp.status_code}")
    content_type = resp.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        return VerifyResult(False, "unreachable", f"Expected an image, got content-type '{content_type or 'unknown'}'")
    return VerifyResult(True, "ok", f"Snapshot image ({content_type}).")


async def _verify_mjpeg(client: httpx.AsyncClient, url: str) -> VerifyResult:
    max_bytes = config.WEBCAM_VERIFY_MJPEG_MAX_BYTES
    try:
        async with client.stream("GET", url) as resp:
            if resp.status_code >= 400:
                return VerifyResult(False, "unreachable", f"HTTP {resp.status_code}")
            content_type = resp.headers.get("content-type", "")
            if "multipart/x-mixed-replace" not in content_type:
                return VerifyResult(
                    False, "unreachable",
                    f"Expected an MJPEG stream (multipart/x-mixed-replace), got '{content_type or 'unknown'}'",
                )
            total = 0
            try:
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total >= max_bytes:
                        break
            except httpx.ReadTimeout:
                # A live MJPEG stream never closes on its own - timing out
                # mid-read after we've already seen bytes IS the success
                # signal, not a failure.
                if total == 0:
                    return VerifyResult(False, "unreachable", "Stream timed out before producing any data.")
            if total == 0:
                return VerifyResult(False, "unreachable", "Stream produced no data.")
            return VerifyResult(True, "ok", f"MJPEG stream confirmed ({total} bytes read).")
    except httpx.TimeoutException:
        return VerifyResult(False, "unreachable", "Timed out connecting to stream.")


async def _verify_hls(client: httpx.AsyncClient, url: str) -> VerifyResult:
    resp = await client.get(url)
    if resp.status_code >= 400:
        return VerifyResult(False, "unreachable", f"HTTP {resp.status_code}")
    text = resp.text
    if "#EXTM3U" not in text[:200]:
        return VerifyResult(False, "unreachable", "Not a valid HLS playlist (missing #EXTM3U).")

    if "#EXT-X-STREAM-INF" in text:
        # Master playlist - resolve and check one level of the first variant.
        variant_url = None
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF"):
                for candidate in lines[i + 1:]:
                    candidate = candidate.strip()
                    if candidate and not candidate.startswith("#"):
                        variant_url = urljoin(url, candidate)
                        break
                if variant_url:
                    break
        if not variant_url:
            return VerifyResult(False, "unreachable", "Master playlist lists no variant streams.")
        variant_resp = await client.get(variant_url)
        if variant_resp.status_code >= 400:
            return VerifyResult(False, "unreachable", f"Variant playlist HTTP {variant_resp.status_code}")
        variant_text = variant_resp.text
        if "#EXTM3U" not in variant_text[:200] or "#EXTINF" not in variant_text:
            return VerifyResult(False, "unreachable", "Variant playlist has no segments.")
        return VerifyResult(True, "ok", "HLS master playlist with a playable variant stream.")

    if "#EXTINF" in text:
        return VerifyResult(True, "ok", "HLS media playlist with segments.")

    return VerifyResult(False, "unreachable", "Playlist has no segments or variant streams.")


async def _verify_youtube(client: httpx.AsyncClient, url: str) -> VerifyResult:
    video_id = extract_youtube_id(url)
    if not video_id:
        return VerifyResult(False, "unsupported", "Could not extract a YouTube video ID from this URL.")

    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    oembed_url = f"https://www.youtube.com/oembed?url={quote(watch_url, safe='')}&format=json"
    resp = await client.get(oembed_url)
    if resp.status_code == 200:
        return VerifyResult(True, "ok", "YouTube video exists and is embeddable.")
    if resp.status_code in (401, 403):
        return VerifyResult(False, "unreachable", "Embedding is disabled by the video's uploader.")
    if resp.status_code == 404:
        return VerifyResult(False, "unreachable", "Video not found, private, or removed.")
    return VerifyResult(False, "unreachable", f"YouTube oEmbed check failed (HTTP {resp.status_code}).")


async def _verify_webpage(client: httpx.AsyncClient, url: str) -> VerifyResult:
    # Webpages are never treated as embeddable live players regardless of
    # outcome - this is a reachability check only, kept separate from
    # "playable" so callers must check kind before offering an inline player.
    try:
        async with client.stream("GET", url) as resp:
            if resp.status_code >= 400:
                return VerifyResult(False, "unreachable", f"HTTP {resp.status_code}")
            return VerifyResult(
                True, "ok",
                "Page is reachable, but webpage sources are reachability-checked only - "
                "they can't be shown as a live player.",
            )
    except httpx.TimeoutException:
        return VerifyResult(False, "unreachable", "Timed out connecting to page.")


_VERIFIERS = {
    "snapshot": _verify_snapshot,
    "mjpeg": _verify_mjpeg,
    "hls": _verify_hls,
    "youtube": _verify_youtube,
    "webpage": _verify_webpage,
}


async def verify_webcam(url: str, kind: str, *, client: Optional[httpx.AsyncClient] = None) -> VerifyResult:
    """Fetch `url` and check whether it looks like a genuine, playable feed
    of the claimed `kind`. Pass a shared `client` when checking many sources
    in a batch (e.g. the health-check job); otherwise a short-lived client is
    opened and closed for this single check."""
    verifier = _VERIFIERS.get(kind)
    if verifier is None:
        return VerifyResult(False, "unsupported", f"Unknown webcam kind '{kind}'.")

    owns_client = client is None
    if owns_client:
        client = _new_client(config.WEBCAM_VERIFY_TIMEOUT_SECONDS)
    try:
        return await verifier(client, url)
    except httpx.TimeoutException:
        return VerifyResult(False, "unreachable", "Timed out.")
    except httpx.HTTPError as e:
        return VerifyResult(False, "unreachable", f"Request failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error verifying webcam {url} ({kind}): {e}", exc_info=True)
        return VerifyResult(False, "unreachable", f"Unexpected error: {e}")
    finally:
        if owns_client:
            await client.aclose()
