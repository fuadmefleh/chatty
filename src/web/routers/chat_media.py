import asyncio
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src.web import config, media_processing
from src.web.auth import require_api_key, require_api_key_flexible

router = APIRouter(prefix="/api/chatty", tags=["chat_media"])

# ── Interactive chat media ───────────────────────────────────────────────────
# Images/videos the user attaches to a live chat message (see chat_ws.py), and
# images Atlas generates (skills/image_generation/). Distinct from the
# passive ingestion endpoint (routers/media.py): these are part of a live turn
# and get served straight back to the browser rather than mined into memory.
_CHAT_MEDIA_FILENAME_RE = config.CHAT_MEDIA_FILENAME_RE
_CHAT_MEDIA_EXT_TO_MIME = config.CHAT_MEDIA_EXT_TO_MIME


@router.get("/chat-media/{filename}", dependencies=[Depends(require_api_key_flexible)])
async def get_chat_media(filename: str):
    if not _CHAT_MEDIA_FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    uploads_dir = media_processing._chat_uploads_dir().resolve()
    path = (uploads_dir / filename).resolve()
    if uploads_dir not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    ext = filename.rsplit(".", 1)[-1]
    return FileResponse(path, media_type=_CHAT_MEDIA_EXT_TO_MIME.get(ext, "application/octet-stream"))


@router.post("/chat/attachments", dependencies=[Depends(require_api_key)], status_code=201)
async def upload_chat_attachment(file: UploadFile = File(...)):
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type in config.MEDIA_IMAGE_FORMATS:
        kind, ext = "image", config.MEDIA_IMAGE_FORMATS[content_type]
    elif content_type in config.MEDIA_VIDEO_FORMATS:
        kind, ext = "video", config.MEDIA_VIDEO_FORMATS[content_type]
    else:
        raise HTTPException(status_code=415, detail=f"Unsupported content type: {content_type or '(none)'}")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > config.CHAT_ATTACHMENT_MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"Attachment exceeds {config.CHAT_ATTACHMENT_MAX_BYTES:,} byte limit")

    filename = f"{uuid.uuid4()}.{ext}"
    await asyncio.to_thread((media_processing._chat_uploads_dir() / filename).write_bytes, data)

    return {"id": filename, "kind": kind, "url": f"/api/chatty/chat-media/{filename}"}
