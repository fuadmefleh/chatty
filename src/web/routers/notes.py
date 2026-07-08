from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.web import config, state
from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/notes", tags=["notes"], dependencies=[Depends(require_api_key)])


class NoteCreate(BaseModel):
    content: str


class NoteUpdate(BaseModel):
    content: str


@router.get("")
async def get_notes():
    notes = state.notes_manager.get_notes(config.WEB_USER_ID)
    return [n.to_dict() for n in notes]


@router.post("", status_code=201)
async def create_note(body: NoteCreate):
    note = state.notes_manager.add_note(config.WEB_USER_ID, body.content)
    return note.to_dict()


@router.put("/{note_id}")
async def update_note(note_id: str, body: NoteUpdate):
    note = state.notes_manager.update_note(config.WEB_USER_ID, note_id, body.content)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note.to_dict()


@router.delete("/{note_id}")
async def delete_note(note_id: str):
    ok = state.notes_manager.delete_note(config.WEB_USER_ID, note_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"deleted": True}
