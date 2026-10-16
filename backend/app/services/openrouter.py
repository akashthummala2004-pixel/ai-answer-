"""Server-side OpenRouter client with timeouts, retries and error normalisation."""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import LLMError

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}

_STATUS_MESSAGES = {
    400: "OpenRouter rejected the request (bad request). Check the model name and parameters.",
    401: "OpenRouter authentication failed. Check OPENROUTER_API_KEY.",
    402: "OpenRouter account has insufficient credits.",
    403: "OpenRouter refused the request (forbidden or moderated).",
    404: "The requested model was not found on OpenRouter.",
    408: "OpenRouter request timed out.",
    429: "OpenRouter rate limit reached. Try again shortly.",
}


@dataclass
class LLMResult:
    content: str
    model: str
    latency_ms: int
    usage: dict[str, Any] = field(default_factory=dict)


class OpenRouterClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def available(self) -> bool:
        return self.settings.ai_live_available

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResult:
        if not self.available:
            raise LLMError("OpenRouter is not configured (OPENROUTER_API_KEY missing).", kind="not_configured")

        model = model or self.settings.openrouter_default_model
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key.strip()}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.openrouter_app_url,
            "X-Title": self.settings.app_name,
        }
        url = f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions"
        timeout = httpx.Timeout(self.settings.openrouter_timeout_seconds, connect=10)

        attempts = self.settings.openrouter_max_retries + 1
        last_error: LLMError | None = None
        for attempt in range(attempts):
            started = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, headers=headers, json=body)
            except httpx.TimeoutException:
                last_error = LLMError(
                    f"OpenRouter request timed out after {self.settings.openrouter_timeout_seconds:.0f}s.",
                    kind="timeout",
                )
            except httpx.HTTPError as exc:
                last_error = LLMError(f"Could not reach OpenRouter: {exc.__class__.__name__}.", kind="network")
            else:
                latency_ms = int((time.perf_counter() - started) * 1000)
                if response.status_code == 200:
                    return self._parse_success(response, model, latency_ms)
                last_error = self._http_error(response)
                if response.status_code not in _RETRYABLE_STATUS:
                    raise last_error
            if attempt < attempts - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
        assert last_error is not None
        raise last_error

    @staticmethod
    def _http_error(response: httpx.Response) -> LLMError:
        detail = ""
        try:
            detail = response.json().get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            pass
        base = _STATUS_MESSAGES.get(response.status_code, f"OpenRouter returned HTTP {response.status_code}.")
        message = f"{base} {detail}".strip() if detail else base
        return LLMError(message, kind="http_error", status_code=response.status_code)

    @staticmethod
    def _parse_success(response: httpx.Response, model: str, latency_ms: int) -> LLMResult:
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMError("OpenRouter returned a non-JSON response.", kind="bad_response") from exc
        if isinstance(data, dict) and data.get("error"):
            message = data["error"].get("message", "Unknown error") if isinstance(data["error"], dict) else str(data["error"])
            raise LLMError(f"OpenRouter error: {message}", kind="provider_error")
        try:
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("OpenRouter response did not contain a message.", kind="bad_response") from exc
        if not content.strip():
            raise LLMError("The model returned an empty response.", kind="empty_response")
        return LLMResult(
            content=content,
            model=data.get("model", model),
            latency_ms=latency_ms,
            usage=data.get("usage") or {},
        )


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Parse JSON from a model reply, tolerating code fences and surrounding prose."""
    candidates = [text.strip()]
    candidates += [m.strip() for m in _FENCE_RE.findall(text)]
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (ValueError, TypeError):
            continue
    raise LLMError("The model did not return valid JSON.", kind="invalid_json")
