"""Persistent store of WhatsApp chats Chatty is allowed to auto-reply in.

Single JSON file keyed by JID (this app is single-user, same convention as
gmail_token.json rather than watchlist's per-user files). Consumed by
heartbeat_manager.py's _process_whatsapp_managed_chats(), which is the only
thing that actually sends autonomous replies - this module just tracks the
opt-in list and each chat's processing cursor/rate-limit state.
"""
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_FILE = Path(__file__).parent.parent.parent / "data" / "whatsapp_managed_chats.json"


def _load() -> Dict[str, Dict[str, Any]]:
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: Dict[str, Dict[str, Any]]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def list_managed() -> List[Dict[str, Any]]:
    return list(_load().values())


def get_managed(jid: str) -> Optional[Dict[str, Any]]:
    return _load().get(jid)


def is_managed(jid: str) -> bool:
    return jid in _load()


def add_managed(jid: str, name: Optional[str], instructions: Optional[str]) -> Dict[str, Any]:
    # UTC, to match the timestamps whatsapp-bridge stores (new Date().toISOString()
    # is always UTC) - the heartbeat step compares these against message
    # timestamps, so a mismatched timezone would either replay backlog or
    # silently skip genuinely new messages.
    now = datetime.now(timezone.utc).isoformat()
    data = _load()
    entry = {
        "jid": jid,
        "name": name,
        "instructions": instructions,
        "added_at": now,
        "last_processed_ts": now,  # only react to messages from here on, never backlog
        "last_processed_msg_id": None,
        "auto_replies_date": None,
        "auto_replies_count": 0,
    }
    data[jid] = entry
    _save(data)
    return entry


def remove_managed(jid: str) -> bool:
    data = _load()
    if jid not in data:
        return False
    del data[jid]
    _save(data)
    return True


def record_processed(jid: str, ts: str, msg_id: Optional[str]) -> None:
    data = _load()
    if jid not in data:
        return
    data[jid]["last_processed_ts"] = ts
    if msg_id:
        data[jid]["last_processed_msg_id"] = msg_id
    _save(data)


def reply_count_today(jid: str) -> int:
    entry = _load().get(jid)
    if not entry:
        return 0
    today = date.today().isoformat()
    if entry.get("auto_replies_date") != today:
        return 0
    return entry.get("auto_replies_count", 0)


def increment_reply_count(jid: str) -> None:
    data = _load()
    if jid not in data:
        return
    today = date.today().isoformat()
    entry = data[jid]
    if entry.get("auto_replies_date") != today:
        entry["auto_replies_date"] = today
        entry["auto_replies_count"] = 0
    entry["auto_replies_count"] += 1
    _save(data)
