"""Thin async HTTP client for the chatty-notes-api sidecar.

"Notes by Chatty" (infineray.com/chatty/) is fronted by a small Express service
running as a Docker container on localhost. It wraps Ghost's Admin API but
hard-scopes the agent to its own publication (tag chatty-notes): every by-id
operation 404s for a post that is not a chatty-notes post, reserved tags are
stripped, and house style (no em-dashes) is normalized server-side. We only ever
hold a bearer token, never the Ghost Admin key.

This module is the only thing on the Python side that talks to that sidecar,
mirroring the role skills/whatsapp_messages/whatsapp_bridge_client.py plays for
the WhatsApp bridge.
"""
from typing import Any, Dict, List, Optional

import httpx

from src.web import config

_TIMEOUT = 30.0


class BlogClientError(Exception):
    """A non-2xx response from the blog sidecar. Carries the HTTP status so the
    router can translate it (a 404 from the sidecar means the post is not a
    chatty-notes post, or does not exist)."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


def _headers() -> Dict[str, str]:
    # Bearer token only; the Ghost Admin key never reaches this process.
    return {"Authorization": f"Bearer {config.BLOG_API_TOKEN}"}


def is_configured() -> bool:
    return bool(config.BLOG_API_TOKEN)


async def _request(method: str, path: str, *, json: Optional[Dict[str, Any]] = None,
                   params: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{config.BLOG_API_URL}{path}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.request(method, url, json=json, params=params, headers=_headers())
    if resp.status_code >= 400:
        # Surface the sidecar's own error text but never echo request headers.
        detail = ""
        try:
            detail = resp.json().get("error") or resp.text
        except Exception:
            detail = resp.text
        raise BlogClientError(resp.status_code, str(detail)[:500])
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


async def list_posts(status: str = "all") -> List[Dict[str, Any]]:
    data = await _request("GET", "/v1/posts", params={"status": status})
    return (data or {}).get("posts", [])


async def get_post(post_id: str) -> Dict[str, Any]:
    return await _request("GET", f"/v1/posts/{post_id}")


async def create_post(title: str, markdown: str, excerpt: str = "",
                      publish: bool = False) -> Dict[str, Any]:
    """Create a post. Defaults to a draft on purpose: autonomous generation must
    never publish. The scheduler and the /generate route always leave publish
    False; only a human approve action flips a post live."""
    return await _request("POST", "/v1/posts", json={
        "title": title,
        "markdown": markdown,
        "excerpt": excerpt,
        "publish": publish,
    })


async def update_post(post_id: str, **fields: Any) -> Dict[str, Any]:
    # Only send provided fields (title / markdown / excerpt / feature_image).
    body = {k: v for k, v in fields.items() if v is not None}
    return await _request("PUT", f"/v1/posts/{post_id}", json=body)


async def publish(post_id: str) -> Dict[str, Any]:
    return await _request("POST", f"/v1/posts/{post_id}/publish")


async def unpublish(post_id: str) -> Dict[str, Any]:
    return await _request("POST", f"/v1/posts/{post_id}/unpublish")


async def delete_post(post_id: str) -> None:
    await _request("DELETE", f"/v1/posts/{post_id}")
