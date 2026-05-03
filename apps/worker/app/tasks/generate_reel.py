"""
Celery task: generate_reel
Runs the full AI creative generation pipeline:
  image analysis → LLM plan → validate → save ReelVersion → enqueue audio/video tasks
"""

import structlog
from celery import Task
from celery.exceptions import MaxRetriesExceededError

from app.main import celery_app

logger = structlog.get_logger(__name__)


class GenerateReelTask(Task):
    """Custom task class with structured logging and retry tracking."""

    abstract = True

    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: object) -> None:
        logger.error(
            "generate_reel_task.failed",
            task_id=task_id,
            exc_type=type(exc).__name__,
            exc_message=str(exc),
        )

    def on_retry(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: object) -> None:
        logger.warning(
            "generate_reel_task.retry",
            task_id=task_id,
            attempt=self.request.retries,
            exc_type=type(exc).__name__,
        )


@celery_app.task(
    bind=True,
    base=GenerateReelTask,
    queue="generation",
    max_retries=3,
    default_retry_delay=30,
    name="app.tasks.generate_reel.generate_creative_plan_task",
)
def generate_creative_plan_task(self: Task, job_id: str) -> dict:
    """
    Main AI generation task.

    Steps:
    1. Load GenerationJob from DB
    2. Fetch image from S3
    3. Analyze image with ImageAnalysisProvider
    4. Build prompt from reel_planner.md template
    5. Generate creative plan with LLMProvider
    6. Validate output against CreativePlan schema
    7. Run moderation check
    8. Save ReelVersion to DB
    9. Enqueue generate_audio_task and generate_video_task

    Args:
        job_id: UUID string of the GenerationJob to process

    Returns:
        dict with version_id and status
    """
    logger.info("generate_creative_plan_task.start", job_id=job_id)

    try:
        # TODO: Implement full pipeline
        # Steps outlined in docs/AI_PIPELINE.md and .agents/skills/ai-pipeline.md
        # This is a skeleton — see apps/api/app/services/ai/ for provider implementations

        logger.info("generate_creative_plan_task.complete", job_id=job_id)
        return {"job_id": job_id, "status": "complete"}

    except Exception as exc:
        logger.exception("generate_creative_plan_task.error", job_id=job_id)
        try:
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
        except MaxRetriesExceededError:
            logger.error("generate_creative_plan_task.max_retries_exceeded", job_id=job_id)
            # TODO: Update GenerationJob.status = FAILED in DB
            return {"job_id": job_id, "status": "failed", "error": str(exc)}


@celery_app.task(
    bind=True,
    queue="generation",
    max_retries=3,
    default_retry_delay=30,
    name="app.tasks.generate_reel.generate_audio_task",
)
def generate_audio_task(self: Task, version_id: str) -> dict:
    """
    TTS audio generation task.

    Steps:
    1. Load ReelVersion from DB
    2. Call TTSProvider.synthesize(voiceover_text)
    3. Upload audio to S3
    4. Create MediaAsset record
    5. Update ReelVersion.audio_asset_id
    6. Check if video task is also complete → trigger render_reel_task

    Args:
        version_id: UUID string of the ReelVersion to process
    """
    logger.info("generate_audio_task.start", version_id=version_id)
    try:
        # TODO: Implement TTS synthesis pipeline
        logger.info("generate_audio_task.complete", version_id=version_id)
        return {"version_id": version_id, "status": "complete"}
    except Exception as exc:
        logger.exception("generate_audio_task.error", version_id=version_id)
        try:
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
        except MaxRetriesExceededError:
            return {"version_id": version_id, "status": "failed", "error": str(exc)}


@celery_app.task(
    bind=True,
    queue="generation",
    max_retries=2,
    default_retry_delay=60,
    name="app.tasks.generate_reel.generate_video_task",
)
def generate_video_task(self: Task, version_id: str) -> dict:
    """
    AI video generation task.

    Steps:
    1. Load ReelVersion from DB
    2. If VIDEO_PROVIDER == 'none': skip (FFmpeg fallback will handle)
    3. Else: call VideoProvider.generate(video_prompt, image_url, duration)
    4. Poll provider until complete
    5. Download and upload raw video to S3
    6. Create MediaAsset record
    7. Check if audio task is also complete → trigger render_reel_task

    Args:
        version_id: UUID string of the ReelVersion to process
    """
    logger.info("generate_video_task.start", version_id=version_id)
    try:
        # TODO: Implement AI video generation pipeline
        logger.info("generate_video_task.complete", version_id=version_id)
        return {"version_id": version_id, "status": "complete"}
    except Exception as exc:
        logger.exception("generate_video_task.error", version_id=version_id)
        try:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except MaxRetriesExceededError:
            return {"version_id": version_id, "status": "failed", "error": str(exc)}
