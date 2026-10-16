"""Domain exceptions and their HTTP mappings."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class LLMError(Exception):
    """Raised when an OpenRouter request fails or returns unusable output."""

    def __init__(self, message: str, kind: str = "llm_error", status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.status_code = status_code


class StorageError(Exception):
    """Raised when the persistence layer (Supabase or local) fails."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(LLMError)
    async def _llm_error(_: Request, exc: LLMError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": exc.message, "kind": exc.kind})

    @app.exception_handler(StorageError)
    async def _storage_error(_: Request, exc: StorageError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": exc.message, "kind": "storage_error"})
