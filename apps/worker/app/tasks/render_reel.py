"""
Celery task: render_reel
Runs the FFmpeg rendering pipeline to produce the final 9:16 MP4.
"""

import structlog
from celery import Task
from celery.exceptions import MaxRetriesExceededError

from app.main import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    queue="rendering",
    max_retries=1,
    default_retry_delay=30,
    name="app.tasks.render_reel.render_reel_task",
)
def render_reel_task(self: Task, version_id: str) -> dict:
    """
    FFmpeg rendering task.

    Steps:
    1. Load ReelVersion from DB (image_asset, audio_asset, subtitle_lines)
    2. Download image from S3 to temp path
    3. Download audio from S3 if available
    4. Write SRT subtitle file
    5. Call FFmpegRenderer.render(params)
    6. Upload rendered MP4 and thumbnail to S3
    7. Create MediaAsset records for rendered video and thumbnail
    8. Update ReelVersion: rendered_asset_id, thumbnail_asset_id, status=READY_FOR_REVIEW
    9. Update ReelProject.status = READY_FOR_REVIEW
    10. Write RenderJob record (COMPLETE)

    Args:
        version_id: UUID string of the ReelVersion to render
    """
    logger.info("render_reel_task.start", version_id=version_id)
    try:
        # TODO: Implement full render pipeline
        # See: apps/api/app/services/rendering/ffmpeg_renderer.py
        logger.info("render_reel_task.complete", version_id=version_id)
        return {"version_id": version_id, "status": "complete"}
    except Exception as exc:
        logger.exception("render_reel_task.error", version_id=version_id)
        try:
            raise self.retry(exc=exc, countdown=30)
        except MaxRetriesExceededError:
            # TODO: Update ReelVersion.status = FAILED_RENDER
            return {"version_id": version_id, "status": "failed", "error": str(exc)}
