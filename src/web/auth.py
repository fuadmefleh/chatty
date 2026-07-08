"""API-key auth dependency, with per-IP brute-force lockout."""
import hmac
import time

from fastapi import Header, HTTPException, Query, Request

from src.web import config, state

# Per-IP lockout to make the API key impractical to brute force: too many
# wrong guesses in a short window locks that IP out for a cooldown period,
# regardless of whether the latest guess was correct.
AUTH_MAX_ATTEMPTS = 5
AUTH_WINDOW_SECONDS = 60
AUTH_LOCKOUT_SECONDS = 300


def _client_ip(request: Request) -> str:
    # nginx (docker/nginx/default.conf) sets X-Real-IP for every proxied
    # request; request.client.host would otherwise just be the nginx hop.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


def _verify_api_key(provided: str, ip: str) -> None:
    """Shared lockout + constant-time compare, used by both the header-only
    (require_api_key) and header-or-query (require_api_key_flexible) dependencies."""
    now = time.monotonic()

    locked_until = state._auth_locked_until.get(ip)
    if locked_until is not None:
        if now < locked_until:
            retry_after = int(locked_until - now) + 1
            raise HTTPException(
                status_code=429,
                detail="Too many invalid API key attempts. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )
        del state._auth_locked_until[ip]

    if not hmac.compare_digest(provided, config.API_KEY):
        attempts = [t for t in state._auth_failures[ip] if now - t < AUTH_WINDOW_SECONDS]
        attempts.append(now)
        state._auth_failures[ip] = attempts
        if len(attempts) >= AUTH_MAX_ATTEMPTS:
            state._auth_locked_until[ip] = now + AUTH_LOCKOUT_SECONDS
            del state._auth_failures[ip]
            raise HTTPException(
                status_code=429,
                detail="Too many invalid API key attempts. Try again later.",
                headers={"Retry-After": str(AUTH_LOCKOUT_SECONDS)},
            )
        raise HTTPException(status_code=401, detail="Invalid API key")

    state._auth_failures.pop(ip, None)


async def require_api_key(request: Request, x_api_key: str = Header(default="")):
    _verify_api_key(x_api_key, _client_ip(request))


async def require_api_key_flexible(
    request: Request, x_api_key: str = Header(default=""), api_key: str = Query(default=""),
):
    """Same as require_api_key, but also accepts the key as an `api_key` query
    param - needed for chat-media, since plain <img>/<video> tags can't set a
    custom header (mirrors websocket_chat's own `api_key: str = Query(...)` auth)."""
    _verify_api_key(x_api_key or api_key, _client_ip(request))
