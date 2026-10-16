"""FastAPI entry point for AI Answer Verification."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.routers import system, verifications

MAX_REQUEST_BYTES = 31 * 1024 * 1024


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_exception_handlers(app)

    @app.middleware("http")
    async def limit_upload_size(request: Request, call_next):
        # Reject oversized uploads before the multipart body is parsed (3 files x 10 MB plus overhead).
        length = request.headers.get("content-length")
        if request.url.path == "/api/smart-verifications" and length and int(length) > MAX_REQUEST_BYTES:
            return JSONResponse(status_code=413, content={"detail": "Upload is too large. The total limit is 30 MB."})
        return await call_next(request)

    app.include_router(system.router)
    app.include_router(verifications.router)
    return app


app = create_app()
