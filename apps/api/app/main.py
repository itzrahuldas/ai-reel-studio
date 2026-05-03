"""
AI Reel Studio — FastAPI Application Entry Point
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import CorrelationIDMiddleware
from app.db.session import engine

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler — startup and shutdown events."""
    configure_logging()
    logger.info("ai_reel_studio.startup", version=settings.APP_VERSION, env=settings.APP_ENV)
    yield
    logger.info("ai_reel_studio.shutdown")
    await engine.dispose()


def create_app() -> FastAPI:
    """Factory function to create the FastAPI application."""
    app = FastAPI(
        title="AI Reel Studio API",
        description=(
            "Production API for generating, reviewing, and publishing AI-powered Instagram Reels.\n\n"
            "**Auth:** All protected routes require `Authorization: Bearer <token>`.\n\n"
            "**Image Upload Flow:**\n"
            "1. `POST /api/v1/media-assets/upload` (multipart) → returns `asset_id`\n"
            "2. `POST /api/v1/reel-projects` with `source_image_id = asset_id`"
        ),
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.APP_ENV != "production" else None,
        redoc_url="/redoc" if settings.APP_ENV != "production" else None,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API Routers ───────────────────────────────────────────────────────────
    app.include_router(api_v1_router, prefix="/api/v1")

    # ── Static Files (local dev uploads) ─────────────────────────────────────
    # Serves uploaded source images at /static/uploads/<filename>
    # In production, files are served from S3/CDN — this mount is dev-only.
    uploads_dir = os.path.join(settings.LOCAL_STORAGE_PATH, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    app.mount("/static", StaticFiles(directory=settings.LOCAL_STORAGE_PATH), name="static")

    # ── Health Check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"], include_in_schema=True)
    async def health_check() -> dict:
        return {
            "status": "ok",
            "version": settings.APP_VERSION,
            "env": settings.APP_ENV,
            "generation_mode": settings.GENERATION_MODE,
        }

    # ── Global Exception Handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "correlation_id", "unknown")
        logger.exception(
            "unhandled_exception",
            request_id=request_id,
            path=request.url.path,
            exc_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                    "request_id": request_id,
                }
            },
        )

    return app


app = create_app()
