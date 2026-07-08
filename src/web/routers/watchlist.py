from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.web import config, state
from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/watchlist", tags=["watchlist"], dependencies=[Depends(require_api_key)])


class WatchTopicCreate(BaseModel):
    topic: str
    kind: str = "news"


@router.get("")
async def get_watchlist():
    return [t.to_dict() for t in state.watchlist_manager.get_topics(config.WEB_USER_ID)]


@router.post("", status_code=201)
async def create_watch_topic(body: WatchTopicCreate):
    topic = body.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic is required")
    if body.kind not in ("news", "stock", "github"):
        raise HTTPException(status_code=400, detail="kind must be one of: news, stock, github")
    watch_topic = state.watchlist_manager.add_topic(config.WEB_USER_ID, topic, kind=body.kind)
    return watch_topic.to_dict()


@router.delete("/{topic_id}")
async def delete_watch_topic(topic_id: str):
    ok = state.watchlist_manager.remove_topic(config.WEB_USER_ID, topic_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Topic not found")
    return {"deleted": True}
