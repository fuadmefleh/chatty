"""Small shared helpers to dedupe repeated route-handler shapes.

Deliberately not a generic CRUD base class: the manager classes these
handlers call (NotesManager, WatchlistManager, WebcamSourcesManager, ...)
differ in method names and return shapes enough that forcing a shared base
would be a leakier abstraction than the ~10 lines of boilerplate it would
replace. These four helpers cover only the parts that really are identical
byte-for-byte across call sites.
"""
from pathlib import Path

from fastapi import HTTPException


def get_or_404(item, detail: str):
    """Raise 404 if `item` (typically a manager's `.get(id)` result) is None,
    otherwise return it unchanged - lets call sites do
    `x = get_or_404(manager.get(id), "X not found")` inline."""
    if item is None:
        raise HTTPException(status_code=404, detail=detail)
    return item


def require_pending(item, kind: str) -> None:
    """Reject with 409 if a suggestion/request-like object isn't awaiting
    action anymore (already implemented/approved/dismissed/etc)."""
    if item.status != "pending":
        raise HTTPException(status_code=409, detail=f"{kind} is already {item.status}")


def wiki_store_for(memory_dir: Path, web_user_id: str):
    from src.core.wiki_store import WikiStore

    return WikiStore(web_user_id, memory_dir / web_user_id / "long_term")


def require_wiki_type(type_: str) -> None:
    if type_ not in ("entity", "concept"):
        raise HTTPException(status_code=400, detail="type must be 'entity' or 'concept'")
