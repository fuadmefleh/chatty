from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.web import config, state
from src.web.auth import require_api_key

router = APIRouter(tags=["transcriptions"], dependencies=[Depends(require_api_key)])


# ── Transcriptions ───────────────────────────────────────────────────────────
# Raw transcriptions (e.g. iOS voice memos) awaiting automatic mining into
# long-term memory by the heartbeat - not user-editable notes. Listing only
# returns pending ones by default; already-mined ones are archived server-side.
class TranscriptionCreate(BaseModel):
    content: str
    source: str = "ios_app"


@router.get("/api/chatty/transcriptions")
async def get_transcriptions(include_archived: bool = False):
    pending = [{**t.to_dict(), "mined": False} for t in state.transcriptions_manager.get_pending(config.WEB_USER_ID)]
    if not include_archived:
        return pending
    archived = [{**t.to_dict(), "mined": True} for t in state.transcriptions_manager.get_archived(config.WEB_USER_ID)]
    return pending + archived


@router.post("/api/chatty/transcriptions", status_code=201)
async def create_transcription(body: TranscriptionCreate):
    transcription = state.transcriptions_manager.add_transcription(config.WEB_USER_ID, body.content, body.source)
    return transcription.to_dict()


@router.delete("/api/chatty/transcriptions/{transcription_id}")
async def delete_transcription(transcription_id: str):
    ok = state.transcriptions_manager.delete_transcription(config.WEB_USER_ID, transcription_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Transcription not found")
    return {"deleted": True}


@router.get("/api/chatty/transcriptions/{transcription_id}/audio")
async def get_transcription_audio(transcription_id: str):
    path = state.transcriptions_manager.get_audio_path(config.WEB_USER_ID, transcription_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(path, media_type="audio/mp4")


def _find_transcription(transcription_id: str):
    """Look up a transcription by id, pending or archived."""
    all_transcripts = (
        state.transcriptions_manager.get_pending(config.WEB_USER_ID)
        + state.transcriptions_manager.get_archived(config.WEB_USER_ID)
    )
    for t in all_transcripts:
        if t.id == transcription_id:
            return t
    return None


@router.get("/api/chatty/transcriptions/{transcription_id}/segments")
async def get_transcription_segments(transcription_id: str):
    """Structured, time-aligned segments with currently-resolved speaker
    names, for the speaker-labeling page. Fetched lazily per transcript
    (mirrors the audio blob's lazy-load pattern) rather than embedded in the
    main transcriptions list, since most of the list is never expanded."""
    transcription = _find_transcription(transcription_id)
    if transcription is None:
        raise HTTPException(status_code=404, detail="Transcription not found")
    if transcription.segments is None:
        return {"segments": []}

    labels = transcription.speaker_labels or {}
    return {
        "segments": [
            {
                "start": seg.get("start"),
                "end": seg.get("end"),
                "local_speaker": seg.get("local_speaker"),
                "speaker_name": labels.get(seg["local_speaker"]) if seg.get("local_speaker") else None,
                "text": seg.get("text"),
            }
            for seg in transcription.segments
        ]
    }


def _rescan_transcripts_for_speaker(exclude_id: Optional[str] = None) -> int:
    """Re-check every stored transcript's per-file speaker embeddings against
    the roster, staging speaker_labels updates for any newly-matching local
    speakers (never overwriting an existing label). Applied via one batched
    write per file - the "face recognition tags other photos too" moment for
    already-backfilled data.

    Called automatically after each manual label (excluding the transcript
    just labeled, since that one was already updated directly), and also
    exposed as a standalone "rescan unmatched" action a user can trigger any
    time - e.g. after tuning SPEAKER_MATCH_THRESHOLD, or to sweep up anything
    an earlier rescan's threshold missed.

    This only ever stages *candidate* additions from a point-in-time
    snapshot; the actual absent-check is re-done atomically at write time
    (see add_speaker_labels_if_absent) so a manual edit that lands on a
    transcript after this snapshot but before the write can never be
    clobbered."""
    updates: dict = {}
    all_transcripts = (
        state.transcriptions_manager.get_pending(config.WEB_USER_ID)
        + state.transcriptions_manager.get_archived(config.WEB_USER_ID)
    )
    for t in all_transcripts:
        if t.id == exclude_id or not t.speaker_embeddings:
            continue
        labels = t.speaker_labels or {}
        candidates = {}
        for local_speaker, embedding in t.speaker_embeddings.items():
            if labels.get(local_speaker):
                continue
            match = state.speaker_manager.match(config.WEB_USER_ID, embedding)
            if match:
                candidates[local_speaker] = match[0]["name"]
        if candidates:
            updates[t.id] = candidates

    if not updates:
        return 0
    return state.transcriptions_manager.add_speaker_labels_if_absent(config.WEB_USER_ID, updates)


class SpeakerLabelRequest(BaseModel):
    local_speaker: str
    name: Optional[str] = None
    speaker_id: Optional[str] = None


@router.post("/api/chatty/transcriptions/{transcription_id}/label")
async def label_speaker(transcription_id: str, body: SpeakerLabelRequest):
    """Assign a real name to a generic diarization speaker id (e.g.
    "SPEAKER_00") within one transcript, either creating a new roster entry
    or attaching another voice sample to an existing one, then retroactively
    relabels every other stored transcript where that voice already
    appears."""
    transcription = _find_transcription(transcription_id)
    if transcription is None:
        raise HTTPException(status_code=404, detail="Transcription not found")
    if not transcription.speaker_embeddings or body.local_speaker not in transcription.speaker_embeddings:
        raise HTTPException(status_code=400, detail="No voice embedding available for this speaker in this transcript")
    if not body.name and not body.speaker_id:
        raise HTTPException(status_code=400, detail="Provide either name (new speaker) or speaker_id (existing speaker)")

    embedding = transcription.speaker_embeddings[body.local_speaker]

    if body.speaker_id:
        speaker = state.speaker_manager.get_speaker(config.WEB_USER_ID, body.speaker_id)
        if speaker is None:
            raise HTTPException(status_code=404, detail="Speaker not found")
        state.speaker_manager.add_sample(config.WEB_USER_ID, speaker["id"], embedding, transcription_id=transcription_id)
    else:
        speaker = state.speaker_manager.create_speaker(config.WEB_USER_ID, body.name, embedding, transcription_id=transcription_id)

    state.transcriptions_manager.set_speaker_label(config.WEB_USER_ID, transcription_id, body.local_speaker, speaker["name"])

    also_updated = _rescan_transcripts_for_speaker(exclude_id=transcription_id)

    return {"speaker": state.speaker_manager.to_public(speaker), "also_updated_count": also_updated}


# ── Speakers (named voice roster) ────────────────────────────────────────────
class SpeakerRename(BaseModel):
    name: str


@router.get("/api/chatty/speakers")
async def get_speakers():
    return state.speaker_manager.list_speakers(config.WEB_USER_ID)


@router.put("/api/chatty/speakers/{speaker_id}")
async def rename_speaker(speaker_id: str, body: SpeakerRename):
    speaker = state.speaker_manager.rename_speaker(config.WEB_USER_ID, speaker_id, body.name)
    if speaker is None:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return state.speaker_manager.to_public(speaker)


@router.delete("/api/chatty/speakers/{speaker_id}")
async def delete_speaker(speaker_id: str):
    """Remove a speaker from the roster - does not retroactively strip labels
    already written into transcripts, only stops future matching."""
    ok = state.speaker_manager.delete_speaker(config.WEB_USER_ID, speaker_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return {"deleted": True}


@router.post("/api/chatty/speakers/rescan")
async def rescan_speakers():
    """Manually sweep every transcript's unmatched speaker embeddings against
    the full roster right now, rather than waiting for the next manual label
    action to trigger it as a side effect. Useful after tuning
    SPEAKER_MATCH_THRESHOLD, or just to force a fresh pass over anything an
    earlier rescan missed."""
    updated_count = _rescan_transcripts_for_speaker()
    return {"updated_count": updated_count}
