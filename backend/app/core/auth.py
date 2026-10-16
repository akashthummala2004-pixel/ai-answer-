"""Authentication: Supabase Auth when configured, otherwise a local demo user."""

import time
from dataclasses import dataclass

import httpx
from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings

LOCAL_USER_ID = "00000000-0000-0000-0000-000000000000"
_TOKEN_CACHE_TTL = 60
_token_cache: dict[str, tuple[float, "CurrentUser"]] = {}


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None
    access_token: str | None
    is_local: bool


def forget_token(token: str) -> None:
    """Drop a token from the validation cache (used on logout)."""
    _token_cache.pop(token, None)


LOCAL_USER = CurrentUser(id=LOCAL_USER_ID, email="local-demo@mindmasters.local", access_token=None, is_local=True)


async def get_current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if not settings.supabase_enabled:
        return LOCAL_USER

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in required.")
    token = authorization.split(" ", 1)[1].strip()

    cached = _token_cache.get(token)
    if cached and cached[0] > time.time():
        return cached[1]

    try:
        async with httpx.AsyncClient(timeout=settings.supabase_timeout_seconds) as client:
            response = await client.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
                headers={"apikey": settings.supabase_anon_key, "Authorization": f"Bearer {token}"},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service unreachable.") from exc

    if response.status_code != 200:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid. Please sign in again.")

    data = response.json()
    user = CurrentUser(id=data["id"], email=data.get("email"), access_token=token, is_local=False)
    _token_cache[token] = (time.time() + _TOKEN_CACHE_TTL, user)
    return user
