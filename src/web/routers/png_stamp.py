"""Stamp uploaded PNGs with Infineray LLC ownership metadata.

Re-encodes the PNG's pixel data and writes Copyright/Author text chunks
identifying Infineray LLC as the owner. Any pre-existing ancillary chunks are
dropped in the process; image content is unchanged. Ported from the standalone
stamp_owner.py CLI so the same behaviour is available in the web UI.
"""
import asyncio
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from PIL import Image, UnidentifiedImageError
from PIL.PngImagePlugin import PngInfo

from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/png-stamp", tags=["png_stamp"], dependencies=[Depends(require_api_key)])

OWNER = "Infineray LLC"
PNG_STAMP_MAX_BYTES = 50 * 1024 * 1024


def _stamp_owner(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as img:
        img.load()
        # Rebuild from raw pixel data so we start from a clean chunk set, then
        # attach only the ownership metadata we want to write.
        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))

        meta = PngInfo()
        year = datetime.now(timezone.utc).year
        meta.add_text("Copyright", f"Copyright © {year} {OWNER}. All rights reserved.")
        meta.add_text("Author", OWNER)

        out = io.BytesIO()
        clean.save(out, format="PNG", pnginfo=meta)
        return out.getvalue()


@router.post("")
async def stamp_png(file: UploadFile = File(...)):
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    name = file.filename or "image.png"
    if content_type != "image/png" and not name.lower().endswith(".png"):
        raise HTTPException(status_code=415, detail="Only PNG files are supported")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > PNG_STAMP_MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds {PNG_STAMP_MAX_BYTES:,} byte limit")

    try:
        stamped = await asyncio.to_thread(_stamp_owner, data)
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(status_code=422, detail="Could not read the file as a PNG image")

    stem = name[:-4] if name.lower().endswith(".png") else name
    download_name = f"{stem}_owned.png"
    return StreamingResponse(
        io.BytesIO(stamped),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )
