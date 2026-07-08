from fastapi import APIRouter, Depends

from src.managers.trending_manager import run_trending_scan
from src.web import state
from src.web.auth import require_api_key
from src.web.helpers import get_or_404, require_pending
from src.web.routers.requests import _ensure_pi_worker_running

router = APIRouter(
    prefix="/api/chatty/trending-suggestions", tags=["trending"], dependencies=[Depends(require_api_key)]
)


# ── Trending Suggestions (GitHub-trending ideas curated by the heartbeat; ────
# never implemented automatically - the user picks from the menu here) ───────
@router.get("")
async def get_trending_suggestions():
    return [s.to_dict() for s in state.trending_suggestions_manager.list()]


@router.post("/scan")
async def scan_trending_suggestions():
    """Manual "scan now" trigger - bypasses the heartbeat's interval gate."""
    await run_trending_scan(state.skills_manager, state.trending_suggestions_manager)
    return [s.to_dict() for s in state.trending_suggestions_manager.list()]


@router.post("/{suggestion_id}/implement")
async def implement_trending_suggestion(suggestion_id: str):
    suggestion = get_or_404(state.trending_suggestions_manager.get(suggestion_id), "Suggestion not found")
    require_pending(suggestion, "Suggestion")

    req = state.feature_requests_manager.create(suggestion.integration_prompt, source="github_trending")
    _ensure_pi_worker_running()
    updated = state.trending_suggestions_manager.update(suggestion_id, status="implemented", request_id=req.id)
    return updated.to_dict()


@router.post("/{suggestion_id}/dismiss")
async def dismiss_trending_suggestion(suggestion_id: str):
    suggestion = get_or_404(state.trending_suggestions_manager.get(suggestion_id), "Suggestion not found")
    require_pending(suggestion, "Suggestion")

    updated = state.trending_suggestions_manager.update(suggestion_id, status="dismissed")
    return updated.to_dict()


@router.delete("/{suggestion_id}")
async def delete_trending_suggestion(suggestion_id: str):
    get_or_404(state.trending_suggestions_manager.get(suggestion_id), "Suggestion not found")
    state.trending_suggestions_manager.delete(suggestion_id)
    return {"deleted": True}
