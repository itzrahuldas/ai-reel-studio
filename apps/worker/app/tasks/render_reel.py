"""
Celery task: render_reel
Runs the FFmpeg rendering pipeline to produce the final 9:16 MP4.
"""

import asyncio
import uuid

import structlog
from celery import Task
from celery.exceptions import MaxRetriesExceededError

from app.main import celery_app  # noqa: E402

logger = structlog.get_logger(__name__)


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
    """
    logger.info("render_reel_task.start", project_id=project_id, version_id=version_id, render_job_id=render_job_id)
    try:
        from app.services.render_service import _run_render_pipeline_inline
        
        asyncio.run(
            _run_render_pipeline_inline(
                project_id=uuid.UUID(project_id),
                version_id=uuid.UUID(version_id),
                render_job_id=uuid.UUID(render_job_id),
            )
        )
        
        logger.info("render_reel_task.complete", version_id=version_id)
        return {"version_id": version_id, "status": "complete"}
    except Exception as exc:
        logger.exception("render_reel_task.error", version_id=version_id)
        try:
            raise self.retry(exc=exc, countdown=30)
        except MaxRetriesExceededError:
            return {"version_id": version_id, "status": "failed", "error": str(exc)}

