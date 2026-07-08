from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.managers.webcam_discovery import run_webcam_discovery_scan
from src.managers.webcam_manager import WEBCAM_KINDS
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


class WebcamSourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    kind: Optional[str] = None
    location: Optional[str] = None
    enabled: Optional[bool] = None


@router.get("/api/chatty/webcam-sources")
async def get_webcam_sources():
    return [s.to_dict() for s in state.webcam_sources_manager.list()]


@router.post("/api/chatty/webcam-sources", status_code=201)
async def create_webcam_source(body: WebcamSourceCreate):
    name = body.name.strip()
    url = body.url.strip()
    if not name or not url:
        raise HTTPException(status_code=400, detail="name and url are required")
    if body.kind not in WEBCAM_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of: {', '.join(WEBCAM_KINDS)}")
    source = state.webcam_sources_manager.create(
        name=name, url=url, kind=body.kind, location=body.location.strip(),
        enabled=body.enabled, source="manual",
    )
    return source.to_dict()


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
async def approve_webcam_suggestion(suggestion_id: str):
    suggestion = get_or_404(state.webcam_suggestions_manager.get(suggestion_id), "Suggestion not found")
    require_pending(suggestion, "Suggestion")

    new_source = state.webcam_sources_manager.create(
        name=suggestion.name, url=suggestion.url, kind=suggestion.kind,
        location=suggestion.location, enabled=True, source="suggestion",
        suggestion_id=suggestion.id,
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
