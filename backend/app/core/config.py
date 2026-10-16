"""Application settings loaded from environment variables / .env file."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_MARKERS = ("your-", "your_", "replace", "xxxx", "changeme", "<")


def is_configured(value: str | None) -> bool:
    """True when a value is set and is not an obvious placeholder from .env.example."""
    if not value or not value.strip():
        return False
    lowered = value.strip().lower()
    return not any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Mind Masters AI Answer Verification"
    app_env: str = "development"

    # OpenRouter (server-side only, never sent to the browser)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_default_model: str = "openai/gpt-4o-mini"
    openrouter_models: str = (
        "openai/gpt-4o-mini,openai/gpt-4o,anthropic/claude-3.5-haiku,google/gemma-3-27b-it"
    )
    openrouter_timeout_seconds: float = Field(default=60, ge=5, le=300)
    openrouter_max_retries: int = Field(default=1, ge=0, le=3)
    openrouter_app_url: str = "http://localhost:5173"

    # Supabase (optional; local JSON storage is used when not configured)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_timeout_seconds: float = Field(default=15, ge=2, le=60)

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    local_data_dir: str = "data"

    @property
    def ai_live_available(self) -> bool:
        return is_configured(self.openrouter_api_key)

    @property
    def supabase_enabled(self) -> bool:
        return is_configured(self.supabase_url) and is_configured(self.supabase_anon_key)

    @property
    def model_list(self) -> list[str]:
        models = [m.strip() for m in self.openrouter_models.split(",") if m.strip()]
        if self.openrouter_default_model not in models:
            models.insert(0, self.openrouter_default_model)
        return models

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
