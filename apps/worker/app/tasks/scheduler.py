"""
Celery scheduled tasks.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import structlog
from celery import current_app, shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.models import PublishJob, PublishJobStatus

logger = structlog.get_logger(__name__)

PUBLISHING_QUEUE = "publishing"
SCHEDULER_QUEUE = "scheduler"


def _safe_error_message(exc: Exception, max_length: int = 500) -> str:
    """Return a bounded single-line error message for logs and job state."""
    message = str(exc) or type(exc).__name__
    message = message.replace("\r", " ").replace("\n", " ")
    if len(message) > max_length:
        return f"{message[:max_length]}..."
    return message


@asynccontextmanager
async def scheduler_session_scope() -> AsyncIterator[AsyncSession]:
    """Create async SQLAlchemy resources scoped to the current Celery task loop."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
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


async def run_scan_scheduled_jobs() -> None:
    """Scan and enqueue scheduled publish jobs."""
    async with scheduler_session_scope() as db:
        now = datetime.now(UTC)

        # We need to find jobs that are SCHEDULED and their time is now or past
        # We also want to lock them.

        # PostgreSQL SKIP LOCKED would be ideal, but for simplicity here
        # we'll use a basic update...returning query or two-step approach.

        stmt = (
            select(PublishJob)
            .where(
                PublishJob.status == PublishJobStatus.SCHEDULED,
                PublishJob.scheduled_for <= now,
                PublishJob.locked_at.is_(None)
                | (PublishJob.locked_at < now - timedelta(minutes=15)),
            )
            .limit(10)
        )

        jobs = (await db.execute(stmt)).scalars().all()

        for job in jobs:
            try:
                # Lock the job
                job.locked_at = now
                job.execution_attempts += 1
                await db.commit()

                # Check if we should enqueue
                job.status = PublishJobStatus.QUEUED
                job.queued_at = now
                await db.commit()

                logger.info("scheduler.enqueueing_job", job_id=str(job.id))

                if settings.PUBLISH_MODE == "async":
                    task = current_app.send_task(
                        "app.tasks.publish_reel.publish_reel_task",
                        args=[str(job.id)],
                        queue=PUBLISHING_QUEUE,
                    )
                    job.celery_task_id = task.id
                    await db.commit()
                else:
                    # Sync mode for local testing
                    from app.tasks.publish_reel import run_publish_pipeline
                    await run_publish_pipeline(db, str(job.id))

            except Exception as exc:
                await db.rollback()
                logger.exception(
                    "scheduler.failed_to_enqueue",
                    job_id=str(job.id),
                    exc_type=type(exc).__name__,
                    error=_safe_error_message(exc),
                )
                job.status = PublishJobStatus.FAILED
                job.error_message = f"Scheduler failed to enqueue: {_safe_error_message(exc)}"
                try:
                    await db.commit()
                except Exception as commit_exc:
                    await db.rollback()
                    logger.exception(
                        "scheduler.failed_to_mark_job_failed",
                        job_id=str(job.id),
                        exc_type=type(commit_exc).__name__,
                        error=_safe_error_message(commit_exc),
                    )


@shared_task(name="app.tasks.scheduler.scan_scheduled_publish_jobs", queue=SCHEDULER_QUEUE)
def scan_scheduled_publish_jobs() -> str:
    """Celery beat task to scan for scheduled jobs."""
    logger.info("celery.scan_scheduled_publish_jobs.started")
    try:
        asyncio.run(run_scan_scheduled_jobs())
    except Exception as exc:
        logger.exception(
            "celery.scan_scheduled_publish_jobs.failed",
            exc_type=type(exc).__name__,
            error=_safe_error_message(exc),
        )
        raise
    else:
        logger.info("celery.scan_scheduled_publish_jobs.finished")
        return "ok"
