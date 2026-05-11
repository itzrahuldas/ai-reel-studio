"""
Celery task: render_reel
Runs the FFmpeg rendering pipeline to produce the final 9:16 MP4.

Async DB isolation: creates a fresh engine + session per task invocation
inside asyncio.run() so asyncpg futures are never attached to a stale event
loop (same pattern as scheduler_session_scope in tasks/scheduler.py).
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from celery import Task
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.main import celery_app  # noqa: E402

logger = structlog.get_logger(__name__)


def _safe_error_message(exc: Exception, max_length: int = 500) -> str:
    """Return a bounded single-line error message for worker logs."""
    message = str(exc) or type(exc).__name__
    message = message.replace("\r", " ").replace("\n", " ")
    if len(message) > max_length:
        return f"{message[:max_length]}..."
    return message


@asynccontextmanager
async def render_session_scope() -> AsyncIterator[AsyncSession]:
    """
    Create async SQLAlchemy resources scoped to the current Celery task loop.

    A fresh engine is created on every call so asyncpg connection futures are
    always attached to the *current* event loop created by asyncio.run().
    The engine is disposed in `finally` to cleanly release all connections
    before the event loop exits.

    This mirrors scheduler_session_scope() in tasks/scheduler.py and avoids:
      RuntimeError: Task got Future attached to a different loop
    """
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=2,        # render worker has low concurrency; keep pool small
        max_overflow=2,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    try:
        async with session_factory() as db:
            yield db
    finally:
        await engine.dispose()


async def _run_render_with_isolated_session(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    render_job_id: uuid.UUID,
) -> bool:
    """
    Wrap the render pipeline with a per-task DB session.

    Called from asyncio.run() inside render_reel_task so that every
    Celery task invocation gets a fresh engine bound to the *new* event loop.
    """
    from app.services.render_service import _run_render_pipeline_with_db  # noqa: PLC0415

    async with render_session_scope() as db:
        return await _run_render_pipeline_with_db(
            db=db,
            project_id=project_id,
            version_id=version_id,
            render_job_id=render_job_id,
        )


@celery_app.task(
    bind=True,
    queue="rendering",
    max_retries=1,
    default_retry_delay=30,
    name="app.tasks.render_reel.render_reel_task",
)
def render_reel_task(self: Task, project_id: str, version_id: str, render_job_id: str) -> dict:
    """
    FFmpeg rendering task.

    Uses a fresh async engine per invocation — never touches the global
    AsyncSessionLocal so asyncpg futures are always on the correct loop.
    """
    logger.info(
        "render_reel_task.start",
        project_id=project_id,
        version_id=version_id,
        render_job_id=render_job_id,
    )
    try:
        succeeded = asyncio.run(
            _run_render_with_isolated_session(
                project_id=uuid.UUID(project_id),
                version_id=uuid.UUID(version_id),
                render_job_id=uuid.UUID(render_job_id),
            )
        )

        if not succeeded:
            logger.warning(
                "render_reel_task.failed",
                project_id=project_id,
                version_id=version_id,
                render_job_id=render_job_id,
            )
            return {
                "version_id": version_id,
                "render_job_id": render_job_id,
                "status": "failed",
            }

        logger.info(
            "render_reel_task.complete",
            project_id=project_id,
            version_id=version_id,
            render_job_id=render_job_id,
        )
        return {"version_id": version_id, "render_job_id": render_job_id, "status": "complete"}
    except Exception as exc:
        logger.exception(
            "render_reel_task.error",
            project_id=project_id,
            version_id=version_id,
            render_job_id=render_job_id,
            error_type=type(exc).__name__,
            error=_safe_error_message(exc),
        )
        try:
            raise self.retry(exc=exc, countdown=30)
        except MaxRetriesExceededError:
            return {
                "version_id": version_id,
                "render_job_id": render_job_id,
                "status": "failed",
                "error": _safe_error_message(exc),
                "error_type": type(exc).__name__,
            }
