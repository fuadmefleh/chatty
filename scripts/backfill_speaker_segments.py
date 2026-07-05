#!/usr/bin/env python3
"""One-time, resumable backfill: re-run diarization on already-stored audio
so old transcriptions get structured, time-aligned segments (and per-speaker
voice embeddings) instead of only flattened text - needed for the speaker
labeling page to work on recordings made before that page existed.

Safe to re-run: transcriptions that already have `segments` populated are
skipped, so an interrupted run just picks up where it left off. Not wired
into any request path or scheduler - run manually, ideally during low-usage
hours since the STT engine's single GPU worker thread will otherwise add
latency to live transcription while this churns through history.

Usage:
    ./venv/bin/python3 scripts/backfill_speaker_segments.py --dry-run
    ./venv/bin/python3 scripts/backfill_speaker_segments.py --limit 20 --sleep 2
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from dotenv import load_dotenv

load_dotenv()

from skills.transcriptions.transcriptions_manager import TranscriptionsManager

STT_ENGINE_URL = os.getenv("STT_ENGINE_URL", "http://127.0.0.1:8003")


# Audio-chunk transcriptions ingested via _transcribe_and_store_audio have
# always been stored as "[<chunk_start>] (device <id>, <Ns> audio) <text>" -
# but pre-existing records (from before the `header` field existed) never
# had that prefix stored separately, only baked into `content`. Regenerating
# content from segments would otherwise silently drop it. Extract it here so
# regenerate_content can reapply it going forward.
_HEADER_RE = re.compile(r"^(\[[^\]]*\]\s\([^)]*\))\s")


def _extract_header(content: str):
    match = _HEADER_RE.match(content or "")
    return match.group(1) if match else None


def _normalize_segments(stt_result: dict):
    raw_segments = stt_result.get("segments") or []
    if not raw_segments:
        return None
    return [
        {
            "start": seg.get("start"),
            "end": seg.get("end"),
            "local_speaker": seg.get("speaker"),
            "text": (seg.get("text") or "").strip(),
        }
        for seg in raw_segments
    ]


def backfill(user_id: str, dry_run: bool, limit: int, sleep_seconds: float) -> None:
    manager = TranscriptionsManager()
    candidates = manager.get_pending(user_id) + manager.get_archived(user_id)

    todo = []
    for t in candidates:
        if t.segments is not None:
            continue  # already backfilled - idempotency marker
        if not t.audio_filename:
            continue  # nothing to re-diarize
        audio_path = manager.audio_dir / t.audio_filename
        if not audio_path.exists():
            print(f"skip {t.id}: audio file missing ({audio_path})")
            continue
        todo.append((t, audio_path))

    print(f"Found {len(todo)} transcription(s) to backfill for user {user_id!r}"
          f"{' (of ' + str(len(candidates)) + ' total)' if candidates else ''}.")
    if limit:
        todo = todo[:limit]
        print(f"Limiting to first {len(todo)}.")

    if dry_run:
        for t, _ in todo:
            print(f"  would backfill {t.id} ({t.created_at})")
        return

    ok, failed = 0, 0
    for i, (t, audio_path) in enumerate(todo, 1):
        try:
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()
            resp = httpx.post(
                f"{STT_ENGINE_URL}/transcribe",
                files={"file": (audio_path.name, audio_bytes, "audio/mp4")},
                data={"language": "en", "diarize": "true"},
                timeout=120.0,
            )
            resp.raise_for_status()
            result = resp.json()

            segments = _normalize_segments(result)
            speaker_embeddings = result.get("speaker_embeddings") or {}
            header = t.header if t.header is not None else _extract_header(t.content)
            manager.update_transcription(
                user_id, t.id,
                segments=segments if segments is not None else [],
                speaker_embeddings=speaker_embeddings or None,
                header=header,
            )
            ok += 1
            print(f"[{i}/{len(todo)}] backfilled {t.id}"
                  f" ({len(segments) if segments else 0} segments, "
                  f"{len(speaker_embeddings)} speaker embeddings)")
        except Exception as e:
            failed += 1
            print(f"[{i}/{len(todo)}] FAILED {t.id}: {e}")

        if sleep_seconds and i < len(todo):
            time.sleep(sleep_seconds)

    print(f"\nDone. {ok} backfilled, {failed} failed, {len(todo) - ok - failed} skipped mid-run.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", default=os.getenv("WEB_USER_ID", ""), help="User id to backfill (defaults to WEB_USER_ID)")
    parser.add_argument("--dry-run", action="store_true", help="List what would be backfilled without calling the STT engine")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N candidates (0 = no limit)")
    parser.add_argument("--sleep", type=float, default=1.0, help="Seconds to sleep between STT calls (be gentle on the shared GPU worker)")
    args = parser.parse_args()

    if not args.user_id:
        print("No user id given and WEB_USER_ID is not set - pass --user-id.", file=sys.stderr)
        sys.exit(1)

    backfill(args.user_id, args.dry_run, args.limit, args.sleep)
