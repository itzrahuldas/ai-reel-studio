"""
Celery task: generate_reel_mock_task
Runs the full mock AI creative generation pipeline:
  Load job → mark RUNNING → MockLLM → save ReelVersion → mark COMPLETE

This module also contains the legacy task stubs (generate_audio_task,
generate_video_task) which are wired for future implementation.
"""

import asyncio
from datetime import UTC, datetime

import structlog
from celery import Task
from celery.exceptions import MaxRetriesExceededError

from app.main import celery_app  # noqa: E402 — worker's own Celery app

logger = structlog.get_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_sync_db():
    """
    Create a synchronous SQLAlchemy session for use inside Celery tasks.
    Celery tasks run in a synchronous context; we cannot use asyncpg here.
    We use psycopg2 (sync) via a separate engine.
    """
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Convert asyncpg URL to sync psycopg2 URL
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_reel_studio",
    )
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    engine = create_engine(sync_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session()


# ── Main Mock Generation Task ─────────────────────────────────────────────────

class GenerateReelTask(Task):
    """Custom task class with structured logging and retry tracking."""

    abstract = True

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: object,
    ) -> None:
        logger.error(
            "generate_reel_task.failed",
            task_id=task_id,
            exc_type=type(exc).__name__,
            exc_message=str(exc),
        )

    def on_retry(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: object,
    ) -> None:
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
    name="app.tasks.generate_reel.generate_reel_mock_task",
)
def generate_reel_mock_task(
    self: Task,
    project_id: str,
    version_id: str,
    job_id: str,
) -> dict:
    """
    Mock AI generation Celery task.

    Steps:
    1. Load GenerationJob, ReelProject, ReelVersion from DB
    2. Idempotency check — if job is already COMPLETE, return safely
    3. Mark job RUNNING, project SCRIPT_GENERATING
    4. Run MockLLMProvider.generate_creative_plan()
    5. Save generated fields to ReelVersion
    6. Mark version READY_FOR_REVIEW, project READY_FOR_REVIEW, job COMPLETE
    7. Write AuditLog entry

    On failure:
    - Mark job FAILED, project FAILED_SCRIPT
    - Store error_message
    - Log structured error
    - Do NOT crash the worker permanently
    """
    logger.info(
        "generate_reel_mock_task.start",
        project_id=project_id,
        version_id=version_id,
        job_id=job_id,
    )

    db = _get_sync_db()
    try:
        from app.models.models import (
            AuditLog,
            GenerationJob,
            JobStatus,
            ReelProject,
            ReelProjectStatus,
            ReelVersion,
        )

        job = db.get(GenerationJob, job_id)
        project = db.get(ReelProject, project_id)
        version = db.get(ReelVersion, version_id)

        if not job or not project or not version:
            logger.error(
                "generate_reel_mock_task.missing_records",
                project_id=project_id,
                job_id=job_id,
            )
            return {"status": "error", "reason": "missing_records"}

        # ── Idempotency check ─────────────────────────────────────────────────
        if job.status == JobStatus.COMPLETE:
            logger.info(
                "generate_reel_mock_task.already_complete",
                job_id=job_id,
            )
            return {"status": "skipped", "reason": "already_complete"}

        # ── Mark RUNNING ──────────────────────────────────────────────────────
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        project.status = ReelProjectStatus.SCRIPT_GENERATING
        db.commit()

        # ── Run mock AI pipeline (sync wrapper around async mock) ─────────────
        from app.services.ai.mock_provider import MockLLMProvider

        provider = MockLLMProvider()

        async def _run() -> object:
            return await provider.generate_creative_plan(
                prompt=project.prompt,
                context={
                    "tone": project.tone,
                    "duration": project.duration_seconds,
                    "cta": project.cta_text,
                    "language": project.language,
                },
            )

        plan = asyncio.run(_run())

        # ── Validate output (Pydantic already validated in mock, belt+suspenders) ─
        from app.services.ai.base import CreativePlan
        validated = CreativePlan.model_validate(plan.model_dump())

        # ── Save to ReelVersion ───────────────────────────────────────────────
        version.hook = validated.hook
        version.script = validated.script
        version.scenes = [s.model_dump() for s in validated.scenes]
        version.voiceover_text = validated.voiceover_text
        version.subtitle_lines = [sl.model_dump() for sl in validated.subtitle_lines]
        version.caption = validated.caption
        version.hashtags = validated.hashtags
        version.video_prompt = validated.video_prompt
        version.estimated_duration = validated.estimated_duration_seconds
        version.moderation_flags = validated.moderation_flags.model_dump()
        version.status = ReelProjectStatus.READY_FOR_REVIEW

        # ── Finalize job ──────────────────────────────────────────────────────
        job.status = JobStatus.COMPLETE
        job.completed_at = datetime.now(UTC)
        job.output_payload = validated.model_dump(mode="json")

        project.status = ReelProjectStatus.READY_FOR_REVIEW

        # ── Audit Log ─────────────────────────────────────────────────────────
        audit = AuditLog(
            action="reel_generation_completed",
            workspace_id=project.workspace_id,
            user_id=project.created_by,
            resource_type="generation_job",
            resource_id=job.id,
            metadata_={
                "version_id": version_id,
                "provider": "mock",
                "mode": "celery",
            },
        )
        db.add(audit)
        db.commit()

        logger.info(
            "generate_reel_mock_task.complete",
            project_id=project_id,
            version_id=version_id,
            job_id=job_id,
        )
        return {"status": "complete", "version_id": version_id}

    except Exception as exc:
        logger.exception(
            "generate_reel_mock_task.error",
            project_id=project_id,
            job_id=job_id,
            error=str(exc),
        )
        try:
            # Best-effort status update — may fail if DB is also down
            from app.models.models import GenerationJob, JobStatus, ReelProject, ReelProjectStatus
            job = db.get(GenerationJob, job_id)
            project = db.get(ReelProject, project_id)
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(exc)
                job.completed_at = datetime.now(UTC)
            if project:
                project.status = ReelProjectStatus.FAILED_SCRIPT
            db.commit()
        except Exception:
            logger.exception("generate_reel_mock_task.cleanup_error", job_id=job_id)

        try:
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
        except MaxRetriesExceededError:
            logger.error(
                "generate_reel_mock_task.max_retries_exceeded",
                job_id=job_id,
            )
            return {"status": "failed", "error": str(exc)}
    finally:
        db.close()


# ── Legacy task stubs ──────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    queue="generation",
    max_retries=3,
    default_retry_delay=30,
    name="app.tasks.generate_reel.generate_creative_plan_task",
)
def generate_creative_plan_task(self: Task, job_id: str) -> dict:
    """
    Legacy task alias — routes to generate_reel_mock_task for MVP.
    TODO: Implement full AI pipeline (real LLM, vision, TTS).
    """
    logger.info("generate_creative_plan_task.start (legacy stub)", job_id=job_id)
    return {"job_id": job_id, "status": "stub_complete"}


@celery_app.task(
    bind=True,
    queue="generation",
    max_retries=3,
    default_retry_delay=30,
    name="app.tasks.generate_reel.generate_audio_task",
)
def generate_audio_task(self: Task, version_id: str) -> dict:
    """
    TTS audio generation task — stub for future implementation.
    TODO: Implement TTSProvider.synthesize() and upload to S3.
    """
    logger.info("generate_audio_task.start (stub)", version_id=version_id)
    return {"version_id": version_id, "status": "stub_complete"}


@celery_app.task(
    bind=True,
    queue="generation",
    max_retries=2,
    default_retry_delay=60,
    name="app.tasks.generate_reel.generate_video_task",
)
def generate_video_task(self: Task, version_id: str) -> dict:
    """
    AI video generation task — stub for future implementation.
    TODO: Implement VideoProvider.generate() and upload to S3.
    """
    logger.info("generate_video_task.start (stub)", version_id=version_id)
    return {"version_id": version_id, "status": "stub_complete"}
