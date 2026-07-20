from typing import List, Literal, Optional, Tuple

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, model_validator

from src.core.logging_config import get_api_logger
from src.managers.scan_jobs import ScanJob
from src.web import config, state
from src.web.auth import require_api_key

logger = get_api_logger()

router = APIRouter(prefix="/api/chatty/insights", tags=["insights"], dependencies=[Depends(require_api_key)])


@router.get("")
async def get_insights(
    limit: int = Query(default=50, ge=1, le=200),
    min_significance: int = Query(default=1, ge=1, le=5),
    include_ad_hoc: bool = Query(default=False),
):
    insights = state.insights_manager.get_insights(
        config.WEB_USER_ID, limit, min_significance, include_ad_hoc=include_ad_hoc
    )
    return [i.to_dict() for i in insights]


@router.delete("/{insight_id}")
async def delete_insight(insight_id: str):
    ok = state.insights_manager.delete_insight(config.WEB_USER_ID, insight_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Insight not found")
    return {"deleted": True}


# ── On-demand scans ──────────────────────────────────────────────────────────
# Insights otherwise only appear on the heartbeat's schedule (a 60-minute tick
# plus a 24h/4h/12h per-kind gate). These routes bypass that gate entirely.
#
# The work runs here in chatty-web-server rather than being handed to the bot:
# the two are separate processes, so this router calls world_watch.scan_topic
# directly, the same way trending.py calls run_trending_scan.


class ScanRequest(BaseModel):
    mode: Literal["topic", "all", "adhoc"]
    topic_id: Optional[str] = None          # mode="topic"
    topic: Optional[str] = None             # mode="adhoc"
    kind: Literal["news", "stock", "github"] = "news"  # mode="adhoc"

    @model_validator(mode="after")
    def check_mode_fields(self):
        if self.mode == "topic" and not self.topic_id:
            raise ValueError("topic_id is required when mode is 'topic'")
        if self.mode == "adhoc" and not (self.topic or "").strip():
            raise ValueError("topic is required when mode is 'adhoc'")
        return self


def _resolve_targets(req: ScanRequest) -> List[Tuple[str, str]]:
    """Turn a request into the list of (topic, kind) pairs to scan."""
    if req.mode == "adhoc":
        return [(req.topic.strip(), req.kind)]

    if req.mode == "topic":
        topic = state.watchlist_manager.get_topic_by_id(config.WEB_USER_ID, req.topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail="Watchlist topic not found")
        return [(topic.topic, topic.kind)]

    topics = state.watchlist_manager.get_topics(config.WEB_USER_ID)
    if not topics:
        raise HTTPException(status_code=400, detail="Watchlist is empty - nothing to scan")
    return [(t.topic, t.kind) for t in topics]


async def _run_scan(job: ScanJob, ad_hoc: bool) -> None:
    """Execute every target in a job, recording each outcome as it lands.

    Per-target failures are recorded on the target rather than raised: one
    dead source shouldn't discard the insights the other topics produced.
    """
    from src.managers import world_watch

    job.start()
    try:
        for target in job.targets:
            # Re-resolve per target so a topic added mid-scan still gets the
            # right dedup state, and so ad-hoc scans never touch watchlist state.
            watch_topic = None
            if not ad_hoc:
                watch_topic = _find_topic(target.topic, target.kind)

            try:
                result = await world_watch.scan_topic(
                    config.WEB_USER_ID,
                    target.kind,
                    target.topic,
                    topic_id=watch_topic.id if watch_topic else None,
                    seen_markers=list(watch_topic.seen_urls) if watch_topic else [],
                    watchlist_mgr=state.watchlist_manager,
                    insights_mgr=state.insights_manager,
                    ad_hoc=ad_hoc,
                )
                target.state = result.state
                if result.insight is not None:
                    target.insight_id = result.insight.id

            except Exception as e:
                logger.error(f"Scan failed for '{target.topic}' ({target.kind}): {e}", exc_info=True)
                target.state = "error"
                target.error = str(e)

        job.finish()

    except Exception as e:
        # Only the run machinery itself blowing up fails the whole job.
        logger.error(f"Scan job {job.id} failed: {e}", exc_info=True)
        job.fail(str(e))


def _find_topic(topic: str, kind: str):
    for t in state.watchlist_manager.get_topics(config.WEB_USER_ID):
        if t.topic == topic and t.kind == kind:
            return t
    return None


@router.post("/scan", status_code=202)
async def start_scan(req: ScanRequest, background: BackgroundTasks):
    """Kick off an on-demand scan and return immediately with a job id.

    One scan per user at a time - a second request while one is in flight
    gets a 409 with the running job's id, so an impatient double-click can't
    fire duplicate LLM calls.
    """
    running = state.scan_jobs.active_for_user(config.WEB_USER_ID)
    if running is not None:
        raise HTTPException(
            status_code=409,
            detail={"message": "A scan is already running", "job_id": running.id},
        )

    targets = _resolve_targets(req)
    job = state.scan_jobs.create(config.WEB_USER_ID, req.mode, targets)
    background.add_task(_run_scan, job, req.mode == "adhoc")

    return {"job_id": job.id, "status": job.status, "targets": len(job.targets)}


@router.get("/scan/{job_id}")
async def get_scan_status(job_id: str):
    """Poll a scan's progress.

    A 404 here can mean the id was never valid *or* that chatty-web-server
    restarted mid-scan and lost the in-memory job. The frontend treats both
    the same way: stop polling and refetch the feed, since the insight may
    have been written before the restart.
    """
    job = state.scan_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scan job not found")
    return job.to_dict()
