"""
Celery tasks for the Instagram Reels Publish Pipeline.
"""

import asyncio
import traceback
from datetime import UTC, datetime
import uuid

import structlog
from celery import shared_task
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import decrypt_token
from app.db.session import AsyncSessionLocal
from app.integrations.instagram.client import InstagramClient
from app.integrations.instagram.errors import (
    InstagramContainerError,
    InstagramTokenExpiredError,
)
from app.models.models import (
    AuditLog,
    PublishJob,
    PublishJobStatus,
    ReelProject,
    ReelProjectStatus,
    ReelVersion,
    SocialAccount,
    SocialAccountStatus,
    UsageEventType,
)
from app.services.usage_service import consume_usage

logger = structlog.get_logger(__name__)


async def _consume_scheduled_publish_usage(db, job, project, version, social_account) -> bool:
    """Consume monthly publish quota when a scheduled publish actually starts."""
    if not job.scheduled_for:
        return True

    try:
        await consume_usage(
            db=db,
            workspace_id=project.workspace_id,
            user_id=social_account.connected_by_user_id or project.created_by,
            event_type=UsageEventType.PUBLISH,
            quantity=1,
            related_project_id=project.id,
            related_version_id=version.id,
            related_job_id=str(job.id),
            metadata_json={"source": "scheduled_publish_execution"},
        )
    except HTTPException as exc:
        if exc.status_code != 402:
            raise

        detail = exc.detail if isinstance(exc.detail, dict) else {}
        job.status = PublishJobStatus.FAILED
        job.error_message = detail.get("message", "Usage limit exceeded for scheduled publish.")
        job.output_payload = {
            "error_code": "USAGE_LIMIT_EXCEEDED",
            "usage_limit": detail,
        }
        project.status = ReelProjectStatus.READY_TO_PUBLISH
        version.status = ReelProjectStatus.READY_TO_PUBLISH
        await db.commit()
        logger.warning("publish.usage_limit_exceeded", job_id=str(job.id), detail=detail)
        return False

    return True


async def run_publish_pipeline(db, publish_job_id: str) -> None:
    """Core async publishing pipeline."""
    job = await db.get(PublishJob, uuid.UUID(publish_job_id))
    if not job:
        logger.error("publish.job_not_found", job_id=publish_job_id)
        return

    # Idempotency check
    if job.status in [PublishJobStatus.PUBLISHED, PublishJobStatus.CANCELLED]:
        logger.info("publish.job_already_terminal", job_id=publish_job_id, status=job.status)
        return

    # Mark started
    if not job.started_at:
        job.started_at = datetime.now(UTC)

    project = await db.get(ReelProject, job.project_id)
    version = await db.get(ReelVersion, job.version_id)
    social_account = await db.get(SocialAccount, job.social_account_id)

    if not project or not version or not social_account:
        job.status = PublishJobStatus.FAILED
        job.error_message = "Missing related project, version, or social account"
        await db.commit()
        return

    if not await _consume_scheduled_publish_usage(db, job, project, version, social_account):
        return

    # Start validation
    try:
        input_payload = job.input_payload or {}
        video_url = input_payload.get("video_url")
        caption = input_payload.get("caption", "")
        share_to_feed = input_payload.get("share_to_feed", True)

        if not video_url:
            raise ValueError("No video_url found in job input_payload")

        if settings.INSTAGRAM_INTEGRATION_MODE == "mock":
            logger.info("publish.mock_mode", job_id=publish_job_id)
            await asyncio.sleep(2)  # Simulate container creation
            job.status = PublishJobStatus.CONTAINER_CREATED
            job.ig_container_id = f"mock_container_{publish_job_id}"
            await db.commit()

            await asyncio.sleep(3)  # Simulate processing
            job.status = PublishJobStatus.PUBLISHED
            job.ig_media_id = f"mock_media_{publish_job_id}"
            job.published_at = datetime.now(UTC)
            job.output_payload = {"mock": True, "permalink": f"https://instagram.com/reel/mock_{publish_job_id}"}
            
            project.status = ReelProjectStatus.PUBLISHED
            version.status = ReelProjectStatus.PUBLISHED
            await db.commit()
            return

        # Live mode
        if not social_account.access_token_encrypted:
            raise InstagramTokenExpiredError("No access token found")
            
        try:
            decrypted_token = decrypt_token(social_account.access_token_encrypted)
        except Exception:
            raise InstagramTokenExpiredError("Could not decrypt access token")

        client = InstagramClient(access_token=decrypted_token)

        # 1. Create Container
        if not job.ig_container_id:
            container_id = await client.create_media_container(
                ig_user_id=social_account.ig_user_id,
                video_url=video_url,
                caption=caption,
                share_to_feed=share_to_feed,
            )
            job.ig_container_id = container_id
            job.status = PublishJobStatus.CONTAINER_CREATED
            await db.commit()
        else:
            container_id = job.ig_container_id

        # 2. Poll Container
        job.status = PublishJobStatus.POLLING
        project.status = ReelProjectStatus.IG_PROCESSING
        version.status = ReelProjectStatus.IG_PROCESSING
        await db.commit()

        poll_attempts = 0
        max_attempts = 30
        poll_interval = 10
        is_finished = False

        while poll_attempts < max_attempts:
            status = await client.check_container_status(container_id)
            if status == "FINISHED":
                is_finished = True
                break
            elif status == "ERROR":
                raise InstagramContainerError("Meta API reported container processing error")
            
            poll_attempts += 1
            await asyncio.sleep(poll_interval)

        if not is_finished:
            raise InstagramContainerError(f"Container polling timed out after {max_attempts} attempts")

        # 3. Publish Media
        media_id = await client.publish_media(social_account.ig_user_id, container_id)
        
        job.ig_media_id = media_id
        job.status = PublishJobStatus.PUBLISHED
        job.published_at = datetime.now(UTC)
        job.output_payload = {"media_id": media_id}
        
        project.status = ReelProjectStatus.PUBLISHED
        version.status = ReelProjectStatus.PUBLISHED
        
        log = AuditLog(
            workspace_id=project.workspace_id,
            user_id=social_account.connected_by_user_id,
            action="publish_job_completed",
            resource_type="publish_job",
            resource_id=job.id,
            metadata_={"media_id": media_id},
        )
        db.add(log)
        
        await db.commit()

        logger.info("publish.success", job_id=publish_job_id, media_id=media_id)

    except InstagramTokenExpiredError as e:
        logger.error("publish.token_expired", job_id=publish_job_id, error=str(e))
        job.status = PublishJobStatus.FAILED
        job.error_message = str(e)
        social_account.status = SocialAccountStatus.RECONNECT_REQUIRED
        project.status = ReelProjectStatus.FAILED_INSTAGRAM_PUBLISH
        version.status = ReelProjectStatus.FAILED_INSTAGRAM_PUBLISH
        
        log = AuditLog(
            workspace_id=project.workspace_id,
            user_id=social_account.connected_by_user_id,
            action="publish_failed_token",
            resource_type="publish_job",
            resource_id=job.id,
            metadata_={"error": str(e)},
        )
        db.add(log)
        await db.commit()

    except Exception as e:
        logger.exception("publish.failed", job_id=publish_job_id)
        job.status = PublishJobStatus.FAILED
        job.error_message = str(e)
        project.status = ReelProjectStatus.FAILED_INSTAGRAM_PUBLISH
        version.status = ReelProjectStatus.FAILED_INSTAGRAM_PUBLISH
        
        log = AuditLog(
            workspace_id=project.workspace_id,
            user_id=social_account.connected_by_user_id,
            action="publish_failed",
            resource_type="publish_job",
            resource_id=job.id,
            metadata_={"error": str(e), "traceback": traceback.format_exc()},
        )
        db.add(log)
        await db.commit()


@shared_task(bind=True, name="app.tasks.publish_reel.publish_reel_task", queue="publishing", max_retries=3)
def publish_reel_task(self, publish_job_id: str) -> str:
    """Celery task entry point."""
    logger.info("celery.publish_reel_task.started", job_id=publish_job_id)

    async def _run():
        async with AsyncSessionLocal() as db:
            await run_publish_pipeline(db, publish_job_id)

    asyncio.run(_run())
    logger.info("celery.publish_reel_task.finished", job_id=publish_job_id)
    return publish_job_id
