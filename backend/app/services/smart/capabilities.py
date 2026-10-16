"""Look up whether the configured OpenRouter model accepts image input (cached)."""

import time

import httpx

from app.core.config import Settings

_CACHE_TTL = 3600
_cache: dict[str, tuple[float, bool | None]] = {}
RECOMMENDED_VISION_MODELS = ("openai/gpt-4o-mini", "google/gemma-3-27b-it")


async def supports_images(settings: Settings) -> bool | None:
    """True/False from OpenRouter's model catalogue; None if it could not be determined."""
    model = settings.openrouter_default_model
    cached = _cache.get(model)
    if cached and cached[0] > time.time():
        return cached[1]
    result: bool | None = None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{settings.openrouter_base_url.rstrip('/')}/models")
        if response.status_code == 200:
            entry = next((m for m in response.json().get("data", []) if m.get("id") == model), None)
            if entry is not None:
                result = "image" in (entry.get("architecture") or {}).get("input_modalities", [])
    except (httpx.HTTPError, ValueError):
        result = None
    _cache[model] = (time.time() + (_CACHE_TTL if result is not None else 60), result)
    return result
