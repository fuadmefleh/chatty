from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from skills.gmail import gmail_integration
from src.web import state as app_state
from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/gmail", tags=["gmail"])


# ── Integrations (Gmail reconnect) ───────────────────────────────────────────
# Web-based OAuth reconnect flow. get_gmail_service()'s own flow opens a
# browser on the server host (fine for a one-time local setup, useless for
# fixing an expired token from the dashboard) - this instead sends the user's
# own browser to Google and back via a real redirect_uri.
@router.get("/status", dependencies=[Depends(require_api_key)])
async def gmail_status():
    return gmail_integration.get_gmail_status()


@router.get("/connect-url", dependencies=[Depends(require_api_key)])
async def gmail_connect_url():
    try:
        return {"url": gmail_integration.get_gmail_auth_url()}
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/callback")
async def gmail_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """Google redirects the user's browser straight here after consent - it
    can't carry our X-API-Key header, so this route is unprotected by design
    and instead relies on the one-time `state` issued by connect-url as its
    CSRF/replay guard. Always ends by bouncing the browser back into the
    dashboard's Settings page, success or failure, so the user isn't left
    staring at a bare JSON response."""
    if error or not code or not state:
        return RedirectResponse(url="/settings?gmail=error")
    try:
        gmail_integration.complete_gmail_auth(code, state)
    except Exception as e:
        app_state.logger.error(f"Gmail OAuth callback failed: {e}")
        return RedirectResponse(url="/settings?gmail=error")
    return RedirectResponse(url="/settings?gmail=connected")


@router.post("/disconnect", dependencies=[Depends(require_api_key)])
async def gmail_disconnect():
    gmail_integration.disconnect_gmail()
    return {"status": "disconnected", "reconnect_available": gmail_integration.WEB_CREDENTIALS_FILE.exists()}
