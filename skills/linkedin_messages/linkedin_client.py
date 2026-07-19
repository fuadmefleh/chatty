"""Thin client for LinkedIn's unofficial Voyager web API, via the `linkedin-api`
PyPI package (tomquirk/linkedin-api).

Unlike WhatsApp there's no persistent connection to hold open (Voyager is
just authenticated HTTPS requests), so unlike whatsapp_bridge_client.py this
talks to LinkedIn directly rather than proxying a sidecar process. There's
also no official OAuth flow that grants messaging/feed/connections access to
third-party apps (contrast skills/gmail/), so this authenticates as the
user's real browser session using a session cookie pair (`li_at` +
`JSESSIONID`) copied from their own logged-in browser - the same
unofficial-but-common approach every other "LinkedIn automation" tool uses.

This is reverse-engineered and against LinkedIn's User Agreement. Frequent
polling risks a checkpoint challenge or account restriction - keep calls
on-demand (dashboard loads, explicit tool calls) rather than tight loops.
"""
import json
from typing import Any, Dict, List, Optional

from requests.cookies import RequestsCookieJar

from linkedin_api import Linkedin
from linkedin_api.utils.helpers import get_id_from_urn

from src.core.config import BASE_DIR

SESSION_FILE = BASE_DIR / "data" / "linkedin_session.json"


class LinkedInSessionError(Exception):
    """Raised when there's no stored session, or LinkedIn rejects it (expired/invalid cookie)."""


def _load_session() -> Optional[Dict[str, str]]:
    if not SESSION_FILE.exists():
        return None
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_session(li_at: str, jsessionid: str, profile_name: Optional[str]) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(
        json.dumps({"li_at": li_at, "jsessionid": jsessionid, "profile_name": profile_name}, indent=2),
        encoding="utf-8",
    )


def clear_session() -> None:
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


def is_connected() -> bool:
    return _load_session() is not None


def _build_cookie_jar(li_at: str, jsessionid: str) -> RequestsCookieJar:
    jar = RequestsCookieJar()
    jar.set("li_at", li_at, domain=".linkedin.com", path="/")
    # The library reads this cookie verbatim as the csrf-token header value;
    # LinkedIn expects it quoted (e.g. `"ajax:1234567890"`).
    value = jsessionid if jsessionid.startswith('"') else f'"{jsessionid}"'
    jar.set("JSESSIONID", value, domain=".linkedin.com", path="/")
    return jar


def _build_client(li_at: str, jsessionid: str) -> Linkedin:
    return Linkedin("", "", authenticate=True, cookies=_build_cookie_jar(li_at, jsessionid))


def _profile_summary(profile: Dict[str, Any]) -> Dict[str, Any]:
    mini = profile.get("miniProfile") or {}
    name = f"{mini.get('firstName', '')} {mini.get('lastName', '')}".strip() or None
    urn_id = None
    entity_urn = mini.get("entityUrn")
    if entity_urn:
        try:
            urn_id = get_id_from_urn(entity_urn)
        except Exception:
            urn_id = None
    return {"name": name, "urn_id": urn_id}


def connect(li_at: str, jsessionid: str) -> Dict[str, Any]:
    """Validates the given cookie pair with one profile request, then persists it.

    Returns {"name": str|None, "urn_id": str|None}. Raises LinkedInSessionError
    if the cookies don't produce a valid session.
    """
    li_at = (li_at or "").strip()
    jsessionid = (jsessionid or "").strip()
    if not li_at or not jsessionid:
        raise LinkedInSessionError("Both the li_at cookie and JSESSIONID are required.")

    client = _build_client(li_at, jsessionid)
    try:
        profile = client.get_user_profile(use_cache=False)
    except Exception as e:
        raise LinkedInSessionError(f"LinkedIn rejected this session: {e}") from e
    if not profile or not profile.get("miniProfile"):
        raise LinkedInSessionError(
            "LinkedIn didn't return a profile for this session - the cookie is likely expired or wrong."
        )

    summary = _profile_summary(profile)
    _save_session(li_at, jsessionid, summary["name"])
    return summary


def _get_client() -> Linkedin:
    session = _load_session()
    if not session:
        raise LinkedInSessionError("LinkedIn isn't connected.")
    return _build_client(session["li_at"], session["jsessionid"])


def get_status() -> Dict[str, Any]:
    session = _load_session()
    if not session:
        return {"status": "disconnected", "name": None}
    return {"status": "connected", "name": session.get("profile_name")}


def get_conversations() -> List[Dict[str, Any]]:
    client = _get_client()
    data = client.get_conversations()
    return data.get("elements", [])


def get_conversation_messages(conversation_urn_id: str) -> List[Dict[str, Any]]:
    client = _get_client()
    data = client.get_conversation(conversation_urn_id)
    return data.get("elements", [])


def get_feed_posts(limit: int = 20) -> List[Dict[str, Any]]:
    client = _get_client()
    return client.get_feed_posts(limit=limit) or []


def get_connections() -> List[Dict[str, Any]]:
    client = _get_client()
    profile = client.get_user_profile()
    urn_id = _profile_summary(profile).get("urn_id")
    if not urn_id:
        raise LinkedInSessionError("Couldn't determine the connected profile's own URN id.")
    return client.get_profile_connections(urn_id) or []


# ── Response formatting ──────────────────────────────────────────────────────
# Shared by src/web/routers/linkedin.py (dashboard JSON) and linkedin_parser.py
# (LLM tool text) so the raw Voyager shape only gets normalized in one place.
def format_conversation(convo: Dict[str, Any]) -> Dict[str, Any]:
    participants = convo.get("participants") or []
    names = []
    for p in participants:
        mini = (p.get("com.linkedin.voyager.messaging.MessagingMember") or {}).get("miniProfile", {})
        name = f"{mini.get('firstName', '')} {mini.get('lastName', '')}".strip()
        if name:
            names.append(name)
    last_event = (convo.get("events") or [{}])[0] if convo.get("events") else {}
    snippet = ((last_event.get("eventContent") or {}).get("com.linkedin.voyager.messaging.event.MessageEvent") or {}).get("body")
    return {
        "conversation_id": (convo.get("entityUrn") or "").split(":")[-1],
        "participants": names,
        "last_message": snippet,
        "unread_count": convo.get("unreadCount", 0),
    }


def format_message(event: Dict[str, Any]) -> Dict[str, Any]:
    content = (event.get("eventContent") or {}).get("com.linkedin.voyager.messaging.event.MessageEvent") or {}
    sender_mini = ((event.get("from") or {}).get("com.linkedin.voyager.messaging.MessagingMember") or {}).get("miniProfile", {})
    return {
        "sender": f"{sender_mini.get('firstName', '')} {sender_mini.get('lastName', '')}".strip() or None,
        "message": content.get("body"),
        "timestamp": event.get("createdAt"),
    }


def format_post(post: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "author": post.get("actor_name") or post.get("author"),
        "text": post.get("commentary") or post.get("text"),
        "posted_at": post.get("posted_at") or post.get("created_at"),
        "url": post.get("url"),
    }


def format_connection(person: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": person.get("name"),
        "title": person.get("jobtitle"),
        "location": person.get("location"),
    }
