"""
Celery scheduled tasks.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from celery import shared_task
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.models import PublishJob, PublishJobStatus
from app.tasks.publish_reel import publish_reel_task

logger = structlog.get_logger(__name__)


async def run_scan_scheduled_jobs() -> None:
    """Scan and enqueue scheduled publish jobs."""
    async with AsyncSessionLocal() as db:
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
                    task = publish_reel_task.delay(str(job.id))
                    job.celery_task_id = task.id
                    await db.commit()
                else:
                    # Sync mode for local testing
                    from app.tasks.publish_reel import run_publish_pipeline
                    await run_publish_pipeline(db, str(job.id))

            except Exception as e:
                logger.exception("scheduler.failed_to_enqueue", job_id=str(job.id))
                job.status = PublishJobStatus.FAILED
                job.error_message = f"Scheduler failed to enqueue: {str(e)}"
                await db.commit()


@shared_task(name="app.tasks.scheduler.scan_scheduled_publish_jobs")
def scan_scheduled_publish_jobs() -> str:
    """Celery beat task to scan for scheduled jobs."""
    logger.info("celery.scan_scheduled_publish_jobs.started")
    asyncio.run(run_scan_scheduled_jobs())
    logger.info("celery.scan_scheduled_publish_jobs.finished")
    return "ok"
