from fastapi import APIRouter, Depends, HTTPException, Query

from src.web import config, state
from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/insights", tags=["insights"], dependencies=[Depends(require_api_key)])


@router.get("")
async def get_insights(limit: int = Query(default=50, ge=1, le=200)):
    return [i.to_dict() for i in state.insights_manager.get_insights(config.WEB_USER_ID, limit)]


@router.delete("/{insight_id}")
async def delete_insight(insight_id: str):
    ok = state.insights_manager.delete_insight(config.WEB_USER_ID, insight_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Insight not found")
    return {"deleted": True}
