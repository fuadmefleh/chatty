from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.managers.webcam_discovery import run_webcam_discovery_scan
from src.managers.webcam_manager import WEBCAM_KINDS
from src.managers.webcam_verifier import verify_webcam
from src.web import state
from src.web.auth import require_api_key
from src.web.helpers import get_or_404, require_pending

router = APIRouter(tags=["webcam"], dependencies=[Depends(require_api_key)])


# ── Webcam Sources & Discovery (SearXNG-curated suggestions the user reviews ──
# on the dashboard; approving one adds it to the source list) ────────────────
class WebcamSourceCreate(BaseModel):
    name: str
    url: str
    kind: str = "webpage"
    location: str = ""
    enabled: bool = True
    force: bool = False  # skip the verification gate (e.g. re-adding a known-good source)


class WebcamSuggestionApprove(BaseModel):
    force: bool = False


class WebcamSourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    kind: Optional[str] = None
    location: Optional[str] = None
    enabled: Optional[bool] = None


@router.get("/api/chatty/webcam-sources")
async def get_webcam_sources():
    return [s.to_dict() for s in state.webcam_sources_manager.list()]


@router.get("/api/chatty/webcam-sources/{source_id}")
async def get_webcam_source(source_id: str):
    source = get_or_404(state.webcam_sources_manager.get(source_id), "Source not found")
    return source.to_dict()


@router.post("/api/chatty/webcam-sources", status_code=201)
async def create_webcam_source(body: WebcamSourceCreate):
    name = body.name.strip()
    url = body.url.strip()
    if not name or not url:
        raise HTTPException(status_code=400, detail="name and url are required")
    if body.kind not in WEBCAM_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of: {', '.join(WEBCAM_KINDS)}")

    result = await verify_webcam(url, body.kind)
    if not result.ok and not body.force:
        raise HTTPException(status_code=422, detail={
            "verification_failed": True, "status": result.status, "detail": result.detail,
        })

    source = state.webcam_sources_manager.create(
        name=name, url=url, kind=body.kind, location=body.location.strip(),
        enabled=body.enabled, source="manual",
        verify_status="ok" if result.ok else "broken",
        verify_detail=result.detail,
        last_verified_at=datetime.now().isoformat(),
    )
    return source.to_dict()


@router.post("/api/chatty/webcam-sources/{source_id}/verify")
async def verify_webcam_source(source_id: str):
    """Re-check a saved source's playability on demand (the dashboard's
    "Recheck" button). Always updates status - never blocks or deletes."""
    source = get_or_404(state.webcam_sources_manager.get(source_id), "Source not found")
    result = await verify_webcam(source.url, source.kind)
    updated = state.webcam_sources_manager.update(
        source_id,
        verify_status="ok" if result.ok else "broken",
        verify_detail=result.detail,
        last_verified_at=datetime.now().isoformat(),
    )
    return updated.to_dict()


@router.put("/api/chatty/webcam-sources/{source_id}")
async def update_webcam_source(source_id: str, body: WebcamSourceUpdate):
    get_or_404(state.webcam_sources_manager.get(source_id), "Source not found")
    fields = body.model_dump(exclude_unset=True)
    if "kind" in fields and fields["kind"] not in WEBCAM_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of: {', '.join(WEBCAM_KINDS)}")
    updated = state.webcam_sources_manager.update(source_id, **fields)
    return updated.to_dict()


@router.delete("/api/chatty/webcam-sources/{source_id}")
async def delete_webcam_source(source_id: str):
    ok = state.webcam_sources_manager.delete(source_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"deleted": True}


@router.get("/api/chatty/webcam-suggestions")
async def get_webcam_suggestions():
    return [s.to_dict() for s in state.webcam_suggestions_manager.list()]


@router.post("/api/chatty/webcam-suggestions/scan")
async def scan_webcam_suggestions():
    """Manual "scan now" trigger - bypasses the heartbeat's interval gate."""
    await run_webcam_discovery_scan(state.webcam_sources_manager, state.webcam_suggestions_manager)
    return [s.to_dict() for s in state.webcam_suggestions_manager.list()]


@router.post("/api/chatty/webcam-suggestions/{suggestion_id}/approve")
async def approve_webcam_suggestion(suggestion_id: str, body: WebcamSuggestionApprove = WebcamSuggestionApprove()):
    suggestion = get_or_404(state.webcam_suggestions_manager.get(suggestion_id), "Suggestion not found")
    require_pending(suggestion, "Suggestion")

    # The discovery scan already pre-verifies curated ideas (see
    # webcam_discovery.py), so a fresh suggestion is usually already "ok" -
    # only re-check here if that never happened (e.g. a legacy suggestion
    # from before this field existed) or the link may have gone stale.
    if suggestion.verify_status == "ok":
        result_ok, result_status, result_detail = True, "ok", suggestion.verify_detail
    else:
        result = await verify_webcam(suggestion.url, suggestion.kind)
        result_ok, result_status, result_detail = result.ok, result.status, result.detail
        if not result_ok and not body.force:
            raise HTTPException(status_code=422, detail={
                "verification_failed": True, "status": result_status, "detail": result_detail,
            })

    new_source = state.webcam_sources_manager.create(
        name=suggestion.name, url=suggestion.url, kind=suggestion.kind,
        location=suggestion.location, enabled=True, source="suggestion",
        suggestion_id=suggestion.id,
        verify_status="ok" if result_ok else "broken",
        verify_detail=result_detail,
        last_verified_at=datetime.now().isoformat(),
    )
    updated = state.webcam_suggestions_manager.update(suggestion_id, status="approved", source_id=new_source.id)
    return updated.to_dict()


@router.post("/api/chatty/webcam-suggestions/{suggestion_id}/dismiss")
async def dismiss_webcam_suggestion(suggestion_id: str):
    suggestion = get_or_404(state.webcam_suggestions_manager.get(suggestion_id), "Suggestion not found")
    require_pending(suggestion, "Suggestion")

    updated = state.webcam_suggestions_manager.update(suggestion_id, status="dismissed")
    return updated.to_dict()


@router.delete("/api/chatty/webcam-suggestions/{suggestion_id}")
async def delete_webcam_suggestion(suggestion_id: str):
    get_or_404(state.webcam_suggestions_manager.get(suggestion_id), "Suggestion not found")
    state.webcam_suggestions_manager.delete(suggestion_id)
    return {"deleted": True}
