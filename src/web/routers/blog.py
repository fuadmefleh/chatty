"""Review and publishing API for "Notes by Chatty".

Chatty writes drafts autonomously (see src/managers/blog_writer.py); this router
is the human side: list drafts and published posts, trigger a draft on demand,
edit, and - the only place anything goes public - approve/publish. It proxies the
chatty-notes-api sidecar via src/web/blog_client.py.
"""
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from src.managers import blog_writer
from src.web import blog_client
from src.web.auth import require_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chatty/blog", tags=["blog"], dependencies=[Depends(require_api_key)])

# In-process generation state. Generation is a single slow LLM call; this guards
# against a second concurrent /generate (mirrors the insights one-scan guard).
_gen = {"generating": False, "error": None}


class PostUpdate(BaseModel):
    title: Optional[str] = None
    markdown: Optional[str] = None
    excerpt: Optional[str] = None


def _translate(exc: blog_client.BlogClientError) -> HTTPException:
    # The sidecar 404s for anything outside the chatty-notes publication, so its
    # status codes are meaningful to pass through.
    return HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/posts")
async def list_posts(status: str = "all"):
    try:
        return await blog_client.list_posts(status=status)
    except blog_client.BlogClientError as exc:
        raise _translate(exc)


@router.get("/status")
async def generation_status():
    return {
        "generating": _gen["generating"],
        "error": _gen["error"],
        "configured": blog_client.is_configured(),
        "last_run_at": blog_writer.last_run_at(),
        "next_due_at": blog_writer.next_due_at(),
    }


@router.get("/posts/{post_id}")
async def get_post(post_id: str):
    try:
        return await blog_client.get_post(post_id)
    except blog_client.BlogClientError as exc:
        raise _translate(exc)


async def _run_generation():
    _gen["generating"] = True
    _gen["error"] = None
    # Advance the interval clock so the scheduler will not also fire a draft
    # right after a manual "generate now".
    blog_writer.touch_last_run()
    try:
        await blog_writer.generate_draft()
    except Exception as exc:  # noqa: BLE001 - surface the message to the UI
        logger.exception("On-demand blog generation failed")
        _gen["error"] = str(exc)
    finally:
        _gen["generating"] = False


@router.post("/generate", status_code=202)
async def generate(background_tasks: BackgroundTasks):
    if not blog_client.is_configured():
        raise HTTPException(status_code=503, detail="Blog API token not configured")
    if _gen["generating"]:
        raise HTTPException(status_code=409, detail="A draft is already being generated")
    background_tasks.add_task(_run_generation)
    return {"started": True}


@router.put("/posts/{post_id}")
async def update_post(post_id: str, body: PostUpdate):
    try:
        return await blog_client.update_post(
            post_id, title=body.title, markdown=body.markdown, excerpt=body.excerpt
        )
    except blog_client.BlogClientError as exc:
        raise _translate(exc)


@router.post("/posts/{post_id}/publish")
async def publish_post(post_id: str):
    """The approve action. The only path that makes a post public."""
    try:
        return await blog_client.publish(post_id)
    except blog_client.BlogClientError as exc:
        raise _translate(exc)


@router.post("/posts/{post_id}/unpublish")
async def unpublish_post(post_id: str):
    try:
        return await blog_client.unpublish(post_id)
    except blog_client.BlogClientError as exc:
        raise _translate(exc)


@router.delete("/posts/{post_id}")
async def delete_post(post_id: str):
    try:
        await blog_client.delete_post(post_id)
    except blog_client.BlogClientError as exc:
        raise _translate(exc)
    return {"deleted": True}
