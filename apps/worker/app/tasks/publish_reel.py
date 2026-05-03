"""
Celery task: publish_reel
Handles Instagram Reels publishing via Meta Graph API.
"""

import structlog
from celery import Task
from celery.exceptions import MaxRetriesExceededError

from app.main import celery_app

logger = structlog.get_logger(__name__)

MAX_POLL_ATTEMPTS = 20
POLL_COUNTDOWN_SECONDS = 10


@celery_app.task(
    bind=True,
    queue="publishing",
    max_retries=3,
    default_retry_delay=30,
    name="app.tasks.publish_reel.publish_reel_task",
)
def publish_reel_task(self: Task, publish_job_id: str) -> dict:
    """
    Instagram publishing task — Step 1: Create media container.

    Steps:
    1. Load PublishJob from DB
    2. Verify ReelProject.status == APPROVED
    3. Verify SocialAccount.status == CONNECTED and token not expired
    4. Get S3 signed URL for rendered MP4
    5. Decrypt access token (via encryption.py)
    6. Call InstagramClient.create_media_container(ig_user_id, video_url, caption)
    7. Store container_id in PublishJob
    8. Update PublishJob.status = CONTAINER_CREATED
    9. Write AuditLog entry
    10. Enqueue poll_instagram_status_task

    Args:
        publish_job_id: UUID of the PublishJob to process
    """
    logger.info("publish_reel_task.start", publish_job_id=publish_job_id)
    try:
        # TODO: Implement full publishing pipeline
        # See: apps/api/app/integrations/instagram/client.py
        # See: docs/INSTAGRAM_INTEGRATION.md for the full flow
        logger.info("publish_reel_task.complete", publish_job_id=publish_job_id)
        return {"publish_job_id": publish_job_id, "status": "container_created"}
    except Exception as exc:
        logger.exception("publish_reel_task.error", publish_job_id=publish_job_id)
        try:
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
        except MaxRetriesExceededError:
            # TODO: Update PublishJob.status = FAILED
            # TODO: Write AuditLog entry
            return {"publish_job_id": publish_job_id, "status": "failed", "error": str(exc)}


@celery_app.task(
    bind=True,
    queue="publishing",
    max_retries=20,
    default_retry_delay=POLL_COUNTDOWN_SECONDS,
    name="app.tasks.publish_reel.poll_instagram_status_task",
)
def poll_instagram_status_task(self: Task, publish_job_id: str) -> dict:
    """
    Instagram publishing task — Step 2: Poll container status.

    Steps:
    1. Load PublishJob from DB
    2. Call InstagramClient.check_container_status(container_id)
    3. If FINISHED: call publish_media → store media_id → mark PUBLISHED
    4. If ERROR: mark FAILED → write AuditLog
    5. If IN_PROGRESS: re-enqueue with countdown (up to MAX_POLL_ATTEMPTS)
    6. If EXPIRED: mark FAILED → write AuditLog

    Args:
        publish_job_id: UUID of the PublishJob to poll
    """
    logger.info("poll_instagram_status_task.start", publish_job_id=publish_job_id, attempt=self.request.retries)
    try:
        # TODO: Implement polling logic
        # On FINISHED: call InstagramClient.publish_media()
        # On ERROR/EXPIRED: mark failed
        # On IN_PROGRESS: self.retry(countdown=POLL_COUNTDOWN_SECONDS)
        logger.info("poll_instagram_status_task.complete", publish_job_id=publish_job_id)
        return {"publish_job_id": publish_job_id, "status": "published"}
    except Exception as exc:
        logger.exception("poll_instagram_status_task.error", publish_job_id=publish_job_id)
        try:
            raise self.retry(exc=exc, countdown=POLL_COUNTDOWN_SECONDS)
        except MaxRetriesExceededError:
            logger.error("poll_instagram_status_task.timeout", publish_job_id=publish_job_id)
            # TODO: Mark PublishJob as failed with timeout reason
            return {"publish_job_id": publish_job_id, "status": "failed", "error": "polling_timeout"}
