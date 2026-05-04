"""
Inline publish pipeline for PUBLISH_MODE=sync (dev/test only).

Runs the mock publish flow entirely within the API process without
requiring the Celery worker. Does NOT support live Instagram publishing.
"""

import asyncio
import uuid
from datetime import UTC, datetime

import structlog

logger = structlog.get_logger(__name__)


async def run_publish_pipeline_inline(job_id: str) -> None:
    """
    Mock publish pipeline that runs inside the API process.

    Flow:
    1. Load PublishJob from DB
    2. Mark CONTAINER_CREATED (simulate media container)
    3. Wait briefly (simulate polling)
    4. Mark PUBLISHED with a fake ig_media_id
    5. Update project/version status

    Only used when PUBLISH_MODE=sync. In production, the Celery
    worker picks up the job from the queue and runs the real pipeline.
    """
    await asyncio.sleep(0.1)  # Yield to allow caller to finish committing

    from app.db.session import AsyncSessionLocal
    from app.models.models import (
        AuditLog,
        PublishJob,
        PublishJobStatus,
        ReelProject,
        ReelProjectStatus,
        ReelVersion,
    )

    async with AsyncSessionLocal() as db:
        try:
            job = await db.get(PublishJob, uuid.UUID(job_id))
            if not job:
                logger.error("publish_pipeline_inline_missing_job", job_id=job_id)
                return

            # Idempotency — skip if already processed
            if job.status in (PublishJobStatus.PUBLISHED, PublishJobStatus.CANCELLED):
                logger.info("publish_pipeline_inline_skipped", job_id=job_id, status=job.status)
                return

            project = await db.get(ReelProject, job.project_id)
            version = await db.get(ReelVersion, job.version_id)

            # Step 1: CONTAINER_CREATED
            job.status = PublishJobStatus.CONTAINER_CREATED
            job.ig_container_id = f"mock_container_{uuid.uuid4().hex[:12]}"
            job.started_at = datetime.now(UTC)
            await db.commit()

            # Step 2: Simulate polling delay
            await asyncio.sleep(0.5)

            # Step 3: PUBLISHED
            job.status = PublishJobStatus.PUBLISHED
            job.ig_media_id = f"mock_media_{uuid.uuid4().hex[:12]}"
            job.published_at = datetime.now(UTC)

            if project:
                project.status = ReelProjectStatus.PUBLISHED
            if version:
                version.status = ReelProjectStatus.PUBLISHED

            audit = AuditLog(
                action="publish_completed_mock",
                workspace_id=project.workspace_id if project else None,
                user_id=project.created_by if project else None,
                resource_type="publish_job",
                resource_id=job.id,
                metadata_={"mode": "sync_inline", "ig_media_id": job.ig_media_id},
            )
            db.add(audit)
            await db.commit()

            logger.info(
                "publish_pipeline_inline_complete",
                job_id=job_id,
                ig_media_id=job.ig_media_id,
            )

        except Exception as exc:
            logger.exception("publish_pipeline_inline_error", job_id=job_id, error=str(exc))
            try:
                job = await db.get(PublishJob, uuid.UUID(job_id))
                if job:
                    job.status = PublishJobStatus.FAILED
                    job.error_message = str(exc)
                    await db.commit()
            except Exception:
                logger.exception("publish_pipeline_inline_cleanup_error")
