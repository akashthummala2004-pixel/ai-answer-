"""Health, configuration status and authentication endpoints."""

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.core.auth import CurrentUser, forget_token, get_current_user
from app.core.config import Settings, get_settings
from app.services.smart.capabilities import supports_images

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "ai_mode": "live" if settings.ai_live_available else "offline",
        "storage": "supabase" if settings.supabase_enabled else "local",
        "auth_required": settings.supabase_enabled,
        "default_model": settings.openrouter_default_model,
        "models": settings.model_list,
        # Whether the configured model accepts images / scanned pages (from OpenRouter's catalogue; null = unknown).
        "vision_supported": await supports_images(settings) if settings.ai_live_available else False,
        "web_search": False,  # no external evidence-search service is integrated
    }


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=2000)


async def _supabase_auth(settings: Settings, path: str, body: dict) -> dict:
    if not settings.supabase_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Authentication is disabled in local mode.")
    try:
        async with httpx.AsyncClient(timeout=settings.supabase_timeout_seconds) as client:
            response = await client.post(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/{path}",
                headers={"apikey": settings.supabase_anon_key, "Content-Type": "application/json"},
                json=body,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service unreachable.") from exc
    data = response.json() if response.content else {}
    if response.status_code >= 400:
        message = data.get("error_description") or data.get("msg") or data.get("message") or "Authentication failed."
        raise HTTPException(status.HTTP_401_UNAUTHORIZED if response.status_code in (400, 401) else response.status_code,
                            message)
    return data


def _session(data: dict) -> dict:
    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "expires_in": data.get("expires_in"),
        "user": {"id": (data.get("user") or {}).get("id"), "email": (data.get("user") or {}).get("email")},
    }


@router.post("/auth/login")
async def login(body: Credentials, settings: Settings = Depends(get_settings)) -> dict:
    data = await _supabase_auth(settings, "token?grant_type=password", body.model_dump())
    return _session(data)


@router.post("/auth/signup")
async def signup(body: Credentials, settings: Settings = Depends(get_settings)) -> dict:
    data = await _supabase_auth(settings, "signup", body.model_dump())
    if not data.get("access_token"):
        return {"access_token": None, "message": "Check your email to confirm your account, then sign in."}
    return _session(data)


@router.post("/auth/refresh")
async def refresh(body: RefreshRequest, settings: Settings = Depends(get_settings)) -> dict:
    data = await _supabase_auth(settings, "token?grant_type=refresh_token", body.model_dump())
    return _session(data)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(authorization: str | None = Header(default=None),
                 settings: Settings = Depends(get_settings)) -> Response:
    """Revoke the Supabase session (refresh token) and forget the cached access token."""
    if settings.supabase_enabled and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        forget_token(token)
        try:
            async with httpx.AsyncClient(timeout=settings.supabase_timeout_seconds) as client:
                await client.post(f"{settings.supabase_url.rstrip('/')}/auth/v1/logout",
                                  headers={"apikey": settings.supabase_anon_key, "Authorization": f"Bearer {token}"})
        except httpx.HTTPError:
            pass  # best effort: the client discards its session regardless
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/me")
async def me(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"id": user.id, "email": user.email, "is_local": user.is_local}
