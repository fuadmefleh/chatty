import fnmatch
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from src.web import config
from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/code", tags=["code_browser"], dependencies=[Depends(require_api_key)])


def _is_excluded_component(name: str) -> bool:
    if name.startswith(".") or name in config.CODE_EXCLUDE_DIRS:
        return True
    lower = name.lower()
    return any(fnmatch.fnmatch(lower, pat) for pat in config.CODE_EXCLUDE_FILE_GLOBS)


def _resolve_code_path(rel_path: str) -> Path:
    root = config.PROJECT_ROOT.resolve()
    candidate = (config.PROJECT_ROOT / (rel_path or "").strip().lstrip("/")).resolve()
    try:
        parts = candidate.relative_to(root).parts
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    if any(_is_excluded_component(p) for p in parts):
        raise HTTPException(status_code=403, detail="Path is not browsable")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return candidate


@router.get("/tree")
async def get_code_tree(path: str = Query(default="")):
    target = _resolve_code_path(path)
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    root = config.PROJECT_ROOT.resolve()
    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if _is_excluded_component(child.name):
            continue
        is_dir = child.is_dir()
        entries.append({
            "name": child.name,
            "path": str(child.resolve().relative_to(root)),
            "type": "dir" if is_dir else "file",
            "size": None if is_dir else child.stat().st_size,
        })

    resolved = target.resolve()
    return {
        "path": "" if resolved == root else str(resolved.relative_to(root)),
        "entries": entries,
    }


@router.get("/file")
async def get_code_file(path: str = Query(default="")):
    target = _resolve_code_path(path)
    if not target.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    ext = target.suffix.lower()
    if ext in config.CODE_BINARY_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Binary file — preview not supported")

    size = target.stat().st_size
    if size > config.CODE_MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large to preview ({size:,} bytes, limit {config.CODE_MAX_FILE_BYTES:,})",
        )

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=415, detail="Binary file — preview not supported")

    return {
        "path": str(target.resolve().relative_to(config.PROJECT_ROOT.resolve())),
        "name": target.name,
        "size": size,
        "language": config.CODE_LANGUAGE_MAP.get(ext, "text"),
        "content": content,
    }
