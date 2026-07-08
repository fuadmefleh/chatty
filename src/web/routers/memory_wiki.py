from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.web import config, helpers, state
from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/memory", tags=["memory_wiki"], dependencies=[Depends(require_api_key)])


# ── Memory viewer ─────────────────────────────────────────────────────────────
class WikiPageCreate(BaseModel):
    type: str
    slug: str
    title: str
    summary: str = ""
    body: str = ""
    tags: List[str] = []


class WikiPageUpdate(BaseModel):
    title: str
    summary: str = ""
    body: str = ""
    tags: List[str] = []


class WikiPageRef(BaseModel):
    type: str
    slug: str
    title: str = ""


class ContradictionResolveRequest(BaseModel):
    page_a: WikiPageRef
    page_b: WikiPageRef
    description: str
    guidance: str


class ReorganizeTargetPage(BaseModel):
    type: str
    slug: str
    title: str
    summary: str = ""
    source_pages: List[str] = []
    already_exists: bool = False


class ReorganizeApplyRequest(BaseModel):
    target_pages: List[ReorganizeTargetPage]


def _wiki_page_response(page: dict) -> dict:
    return {
        "title": page["title"],
        "type": page["type"],
        "slug": page["slug"],
        "summary": page["summary"],
        "tags": page["tags"],
        "body": page["body"],
        "updated": page["updated"],
    }


@router.get("")
async def get_memory(days: int = Query(default=7, ge=1, le=90)):
    user_memory_dir = config.MEMORY_DIR / config.WEB_USER_ID
    result = {"short_term": [], "long_term": [], "wiki_index": "", "wiki_log": ""}

    short_term_dir = user_memory_dir / "short_term"
    if short_term_dir.exists():
        files = sorted(short_term_dir.glob("*.md"), key=lambda p: p.stem, reverse=True)[:days]
        for f in files:
            result["short_term"].append({
                "date": f.stem,
                "content": f.read_text(encoding="utf-8"),
                "filename": f.name,
            })

    wiki_store = helpers.wiki_store_for(config.MEMORY_DIR, config.WEB_USER_ID)
    for page in wiki_store.list_pages():
        result["long_term"].append({
            "title": page["title"],
            "type": page["type"],
            "slug": page["slug"],
            "summary": page["summary"],
            "tags": page["tags"],
            "body": page["body"],
            "updated": page["updated"],
        })
    result["wiki_index"] = wiki_store.read_index()
    result["wiki_log"] = wiki_store.read_log(tail=50)

    return result


@router.get("/page/{type}/{slug}")
async def get_memory_page(type: str, slug: str):
    helpers.require_wiki_type(type)

    wiki_store = helpers.wiki_store_for(config.MEMORY_DIR, config.WEB_USER_ID)
    page = wiki_store.get_page(type, slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    return _wiki_page_response(page)


@router.post("/page", status_code=201)
async def create_memory_page(body: WikiPageCreate):
    helpers.require_wiki_type(body.type)

    wiki_store = helpers.wiki_store_for(config.MEMORY_DIR, config.WEB_USER_ID)
    if wiki_store.get_page(body.type, body.slug) is not None:
        raise HTTPException(status_code=409, detail="Page already exists")

    page = wiki_store.write_page(
        type_=body.type, slug=body.slug, title=body.title,
        summary=body.summary, body=body.body, tags=body.tags,
    )
    wiki_store.append_log("manual-edit", f"{page['title']} — created via dashboard")
    return _wiki_page_response(page)


@router.put("/page/{type}/{slug}")
async def update_memory_page(type: str, slug: str, body: WikiPageUpdate):
    helpers.require_wiki_type(type)

    wiki_store = helpers.wiki_store_for(config.MEMORY_DIR, config.WEB_USER_ID)
    if wiki_store.get_page(type, slug) is None:
        raise HTTPException(status_code=404, detail="Page not found")

    page = wiki_store.write_page(
        type_=type, slug=slug, title=body.title,
        summary=body.summary, body=body.body, tags=body.tags,
    )
    wiki_store.append_log("manual-edit", f"{page['title']} — edited via dashboard")
    return _wiki_page_response(page)


@router.delete("/page/{type}/{slug}")
async def delete_memory_page(type: str, slug: str):
    helpers.require_wiki_type(type)

    wiki_store = helpers.wiki_store_for(config.MEMORY_DIR, config.WEB_USER_ID)
    page = wiki_store.delete_page(type, slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    wiki_store.append_log("manual-edit", f"{page['title']} — deleted via dashboard")
    return {"deleted": True}


@router.get("/page/{type}/{slug}/backlinks")
async def get_memory_page_backlinks(type: str, slug: str):
    helpers.require_wiki_type(type)

    wiki_store = helpers.wiki_store_for(config.MEMORY_DIR, config.WEB_USER_ID)
    if wiki_store.get_page(type, slug) is None:
        raise HTTPException(status_code=404, detail="Page not found")

    backlinks = wiki_store.get_backlinks(type, slug)
    return [
        {"title": p["title"], "type": p["type"], "slug": p["slug"], "summary": p["summary"]}
        for p in backlinks
    ]


@router.get("/health")
async def get_memory_health():
    wiki_store = helpers.wiki_store_for(config.MEMORY_DIR, config.WEB_USER_ID)
    health = wiki_store.read_health()
    if health is None:
        return {
            "generated_at": None,
            "total_pages": len(wiki_store.list_pages()),
            "auto_fixed": {},
            "orphans": [],
            "contradictions": [],
            "coverage_gaps": [],
        }
    return health


@router.post("/lint")
async def lint_memory():
    from src.core.memory import MemoryManager

    memory_manager = MemoryManager(config.WEB_USER_ID)
    result = await memory_manager.lint_wiki()
    return {"result": result}


@router.post("/health/resolve-contradiction")
async def resolve_memory_contradiction(body: ContradictionResolveRequest):
    """Runs the full StagedReACTAgent tool loop (not a bespoke fix script),
    so it's genuinely slow - a couple of minutes is normal. Deliberately
    does NOT also re-run lint_wiki() afterward: that adds its own
    multi-minute full-wiki LLM contradiction/gap scan on top, which nearly
    doubles an already-slow request for a snapshot the frontend doesn't
    strictly need synchronously (it drops the card optimistically instead;
    a fresh contradiction list is one "Run lint now" click away)."""
    from src.core.memory import MemoryManager
    from src.agents.staged_react_agent import StagedReACTAgent

    memory_manager = MemoryManager(config.WEB_USER_ID)
    agent = StagedReACTAgent(memory_manager, state.skills_manager)
    result = await memory_manager.resolve_contradiction(
        body.page_a.model_dump(), body.page_b.model_dump(), body.description, body.guidance, agent,
    )
    return {"result": result}


@router.post("/reorganize/propose")
async def propose_memory_reorganization():
    """Read-only: one LLM call over the whole wiki proposing a more
    granular target page structure. Nothing is written - the frontend
    shows this plan for review before /reorganize/apply executes it."""
    from src.core.memory import MemoryManager

    memory_manager = MemoryManager(config.WEB_USER_ID)
    return await memory_manager.propose_reorganization()


@router.post("/reorganize/apply")
async def apply_memory_reorganization(body: ReorganizeApplyRequest):
    """Executes a (possibly user-trimmed) plan from /reorganize/propose.
    Only ever creates/overwrites the listed target pages - never deletes
    their source pages, so this is safe to re-run and safe to review
    afterward before manually cleaning up stale pages."""
    from src.core.memory import MemoryManager

    memory_manager = MemoryManager(config.WEB_USER_ID)
    result = await memory_manager.apply_reorganization([t.model_dump() for t in body.target_pages])
    return {"result": result}


@router.get("/search")
async def search_memory(q: str = Query(min_length=1)):
    from src.core.memory_tools import MemoryTools

    memory_tools = MemoryTools(config.WEB_USER_ID)
    results = await memory_tools.search_memory_grep(q)
    return {"results": results}


@router.post("/consolidate")
async def consolidate_memory():
    from src.core.memory import MemoryManager
    from src.agents.staged_react_agent import StagedReACTAgent

    memory_manager = MemoryManager(config.WEB_USER_ID)
    agent = StagedReACTAgent(memory_manager, state.skills_manager)
    result = await memory_manager.consolidate_memories(agent)
    return {"result": result}
