import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from skills.pi_agent import lock as pi_lock
from src.managers.self_upgrade_manager import run_feature_request
from src.web import config, state
from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/requests", tags=["requests"], dependencies=[Depends(require_api_key)])


# ── Feature Requests (routed to the local Pi + qwen3.6-27b coding agent) ──────
class FeatureRequestCreate(BaseModel):
    prompt: str


async def _process_pi_queue():
    """Drain queued feature requests one at a time through the Pi agent.

    Each request runs inside an isolated git worktree via
    src.managers.self_upgrade_manager.run_feature_request - the same
    pattern the heartbeat's self-upgrade pipeline uses - so Pi can never
    edit the live checkout mid-turn, and never restarts the very server
    it's running under as its own verification step (that used to kill the
    `pi` subprocess before it could report back; see
    skills/pi_agent/runner.py's PM2_SELF_APP_NAME handling for the narrower
    fix covering requests made before this existed).
    """
    try:
        while True:
            req = state.feature_requests_manager.next_queued()
            if req is None:
                break

            state.feature_requests_manager.update(req.id, status="running")

            # Coordinate with the heartbeat's self-upgrade pipeline (a separate
            # process) so two `pi` runs never touch the repo at once. Bounded
            # wait so a stuck self-upgrade can't permanently wedge this queue.
            waited = 0
            while not pi_lock.acquire("web_queue"):
                if waited >= 900:  # 15 min
                    state.feature_requests_manager.append_log(
                        req.id, "Proceeding despite an active self-upgrade lock (waited 15 min)."
                    )
                    break
                await asyncio.sleep(5)
                waited += 5

            try:
                await run_feature_request(req.id, req.prompt, state.feature_requests_manager)
            except Exception as e:
                state.feature_requests_manager.update(req.id, status="error", summary=str(e))
            finally:
                pi_lock.release("web_queue")

            # Safety net: if run_feature_request ended without setting a terminal status
            latest = state.feature_requests_manager.get(req.id)
            if latest and latest.status in ("running", "testing"):
                state.feature_requests_manager.update(req.id, status="completed", summary="Finished.")
    finally:
        state._pi_worker_task = None


def _ensure_pi_worker_running():
    if state._pi_worker_task is None or state._pi_worker_task.done():
        state._pi_worker_task = asyncio.create_task(_process_pi_queue())


@router.get("")
async def get_requests():
    return [r.to_dict() for r in state.feature_requests_manager.list()]


@router.post("", status_code=201)
async def create_request(body: FeatureRequestCreate):
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    req = state.feature_requests_manager.create(prompt)
    _ensure_pi_worker_running()
    return req.to_dict()


@router.delete("/{request_id}")
async def delete_request(request_id: str):
    req = state.feature_requests_manager.get(request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status == "running":
        raise HTTPException(status_code=409, detail="Cannot delete a running request")
    state.feature_requests_manager.delete(request_id)
    return {"deleted": True}


@router.post("/retry-merges")
async def retry_merges():
    """Manually trigger a retry of any requests deferred by the merge safety
    gate (main was dirty, or checked out to something other than main) -
    the same retry_pending_merges() the heartbeat already calls every tick
    (see HeartbeatManager._process_pending_merges), just on demand instead of
    waiting up to HEARTBEAT_INTERVAL_MINUTES. No chat message is sent - the
    dashboard itself shows the result."""
    from src.managers import self_upgrade_manager

    summaries = await self_upgrade_manager.retry_pending_merges(
        state.feature_requests_manager, send_message_callback=None, user_id=config.WEB_USER_ID
    )
    return {"summaries": summaries}
