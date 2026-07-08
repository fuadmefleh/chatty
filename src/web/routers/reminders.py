import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from src.web import config
from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/reminders", tags=["reminders"], dependencies=[Depends(require_api_key)])


def _load_reminders() -> List[dict]:
    reminders = []
    if not config.REMINDERS_DIR.exists():
        return reminders
    for f in sorted(config.REMINDERS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            data["_file"] = f.name
            reminders.append(data)
        except Exception:
            pass
    return reminders


@router.get("")
async def get_reminders():
    return _load_reminders()


@router.delete("/{filename}")
async def delete_reminder(filename: str):
    # Security: only allow .json files within REMINDERS_DIR
    if "/" in filename or "\\" in filename or not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    target = config.REMINDERS_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="Reminder not found")
    target.unlink()
    return {"deleted": True}
