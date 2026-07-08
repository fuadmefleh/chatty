import importlib.util

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from skills.video_production import video_manager as _video_mgr
from src.web import config
from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/video-jobs", tags=["video_production"], dependencies=[Depends(require_api_key)])

# Import video_api via importlib to mirror the skill's own pattern
_video_api_path = config.PROJECT_ROOT / "skills" / "video_production" / "video_api.py"
_video_api_spec = importlib.util.spec_from_file_location("video_production_webapi", _video_api_path)
_video_api = importlib.util.module_from_spec(_video_api_spec)
_video_api_spec.loader.exec_module(_video_api)

_VALID_DURATIONS = [2, 4, 6, 8, 10, 15]
_VALID_RESOLUTIONS = ["480p", "720p", "1080p", "auto"]


class VideoJobCreate(BaseModel):
    prompt: str
    duration_seconds: int = 4
    resolution: str = "auto"


@router.get("")
async def get_video_jobs(limit: int = Query(default=50, ge=1, le=200)):
    return _video_mgr.list_jobs(limit=limit)


@router.post("", status_code=201)
async def create_video_job(body: VideoJobCreate, background_tasks: BackgroundTasks):
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    if body.duration_seconds not in _VALID_DURATIONS:
        raise HTTPException(status_code=400, detail=f"duration_seconds must be one of: {_VALID_DURATIONS}")
    if body.resolution not in _VALID_RESOLUTIONS:
        raise HTTPException(status_code=400, detail=f"resolution must be one of: {_VALID_RESOLUTIONS}")

    # Create the job record
    job = _video_mgr.create_job(
        prompt=prompt,
        duration_seconds=body.duration_seconds,
        resolution=body.resolution,
    )

    # Kick off actual video generation in the background
    async def _run_generation(job_id: str):
        _video_mgr.update_job(job_id, status="generating")
        try:
            result = await _video_api.generate_video(
                prompt,
                duration_seconds=body.duration_seconds,
                resolution=body.resolution,
            )
            if result.get("success"):
                _video_mgr.update_job(job_id, status="completed", url=result.get("url"))
            else:
                _video_mgr.update_job(job_id, status="failed", error=result.get("error", "unknown error"))
        except Exception as e:
            _video_mgr.update_job(job_id, status="failed", error=str(e))

    background_tasks.add_task(_run_generation, job["id"])
    return job


@router.get("/{job_id}")
async def get_video_job(job_id: str):
    job = _video_mgr.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}")
async def delete_video_job(job_id: str):
    ok = _video_mgr.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"deleted": True}
