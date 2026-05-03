"""
Reel project service — create, list, retrieve, and enqueue mock generation.
"""

import uuid
from typing import Any

import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import (
    AuditLog,
    GenerationJob,
    JobStatus,
    ReelProject,
    ReelProjectStatus,
    ReelVersion,
    WorkspaceMember,
)
from app.schemas.schemas import CreateReelProjectRequest

logger = structlog.get_logger(__name__)


# ── Workspace Resolution ──────────────────────────────────────────────────────

async def get_user_workspace_id(
    db: AsyncSession,
    user_id: uuid.UUID,
    provided_workspace_id: uuid.UUID | None,
) -> uuid.UUID:
    """Resolve workspace_id, validating membership. Returns workspace UUID."""
    if provided_workspace_id:
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == provided_workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        if not (await db.execute(stmt)).scalars().first():
            raise HTTPException(status_code=403, detail="Not a member of this workspace")
        return provided_workspace_id

    stmt = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user_id)
    ws_id = (await db.execute(stmt)).scalars().first()
    if not ws_id:
        raise HTTPException(status_code=400, detail="User has no workspace")
    return ws_id


# ── Create ────────────────────────────────────────────────────────────────────

async def create_reel_project(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: CreateReelProjectRequest,
) -> tuple[ReelProject, ReelVersion, GenerationJob]:
    """
    Create ReelProject + ReelVersion placeholder + GenerationJob, then
    either enqueue a Celery task (async mode) or run the mock pipeline
    inline (sync mode).
    """
    workspace_id = await get_user_workspace_id(db, user_id, data.workspace_id)

    # ── 1. ReelProject ────────────────────────────────────────────────────────
    project = ReelProject(
        workspace_id=workspace_id,
        created_by=user_id,
        title=data.title or f"Reel: {data.prompt[:40]}…",
        prompt=data.prompt,
        language=data.language,
        tone=data.tone,
        duration_seconds=data.duration_seconds,
        cta_text=data.cta_text,
        source_image_id=data.source_image_id,
        status=ReelProjectStatus.DRAFT,
    )
    db.add(project)
    await db.flush()

    # ── 2. ReelVersion placeholder ────────────────────────────────────────────
    version = ReelVersion(
        project_id=project.id,
        version_number=1,
        status=ReelProjectStatus.DRAFT,
    )
    db.add(version)
    await db.flush()

    project.latest_version_id = version.id

    # ── 3. GenerationJob ──────────────────────────────────────────────────────
    job = GenerationJob(
        project_id=project.id,
        version_id=version.id,
        job_type="mock_generation",
        status=JobStatus.QUEUED,
        input_payload=data.model_dump(mode="json"),
    )
    db.add(job)
    await db.flush()

    # ── 4. Audit Log ──────────────────────────────────────────────────────────
    audit = AuditLog(
        action="reel_project_created",
        workspace_id=workspace_id,
        user_id=user_id,
        resource_type="reel_project",
        resource_id=project.id,
        metadata_={"job_id": str(job.id), "version_id": str(version.id)},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(project)
    await db.refresh(version)
    await db.refresh(job)

    # ── 5. Enqueue task or run inline ─────────────────────────────────────────
    mode = settings.GENERATION_MODE
    if mode == "sync":
        # Run mock pipeline synchronously within the API process
        await _run_mock_pipeline_inline(
            project_id=project.id,
            version_id=version.id,
            job_id=job.id,
            prompt=project.prompt,
            tone=project.tone,
            duration=project.duration_seconds,
            cta=project.cta_text,
        )
        # Refresh to pick up updated status after inline execution
        await db.refresh(project)
        await db.refresh(version)
        await db.refresh(job)
    else:
        try:
            from app.workers.celery_client import celery_client
            celery_client.send_task(
                "app.tasks.generate_reel.generate_reel_mock_task",
                args=[str(project.id), str(version.id), str(job.id)],
                queue="generation",
            )
            logger.info(
                "reel_generation_enqueued",
                project_id=str(project.id),
                job_id=str(job.id),
            )
        except Exception as e:
            logger.warning(
                "celery_enqueue_failed",
                error=str(e),
                hint="Is Redis running? Try GENERATION_MODE=sync for local dev.",
            )

    return project, version, job


# ── Sync inline pipeline (no Celery) ─────────────────────────────────────────

async def _run_mock_pipeline_inline(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    job_id: uuid.UUID,
    prompt: str,
    tone: str | None,
    duration: int,
    cta: str | None,
) -> None:
    """Run mock generation pipeline inline (GENERATION_MODE=sync)."""
    from datetime import UTC, datetime

    from app.db.session import AsyncSessionLocal
    from app.models.models import JobStatus, ReelProjectStatus
    from app.services.ai.mock_provider import MockLLMProvider

    async with AsyncSessionLocal() as db:
        try:
            job = await db.get(GenerationJob, job_id)
            project = await db.get(ReelProject, project_id)
            version = await db.get(ReelVersion, version_id)

            if not job or not project or not version:
                logger.error("sync_pipeline_missing_records", project_id=str(project_id))
                return

            # Mark running
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(UTC)
            project.status = ReelProjectStatus.SCRIPT_GENERATING
            await db.commit()

            # Generate
            llm = MockLLMProvider()
            plan = await llm.generate_creative_plan(
                prompt=prompt,
                context={"tone": tone, "duration": duration, "cta": cta},
            )

            # Save to version
            version.hook = plan.hook
            version.script = plan.script
            version.scenes = [s.model_dump() for s in plan.scenes]
            version.voiceover_text = plan.voiceover_text
            version.subtitle_lines = [sl.model_dump() for sl in plan.subtitle_lines]
            version.caption = plan.caption
            version.hashtags = plan.hashtags
            version.video_prompt = plan.video_prompt
            version.estimated_duration = plan.estimated_duration_seconds
            version.moderation_flags = plan.moderation_flags.model_dump()
            version.status = ReelProjectStatus.READY_FOR_REVIEW

            job.status = JobStatus.COMPLETE
            job.completed_at = datetime.now(UTC)
            job.output_payload = plan.model_dump(mode="json")

            project.status = ReelProjectStatus.READY_FOR_REVIEW

            # Audit
            audit = AuditLog(
                action="reel_generation_completed",
                workspace_id=project.workspace_id,
                user_id=project.created_by,
                resource_type="generation_job",
                resource_id=job.id,
                metadata_={"mode": "sync", "version_id": str(version_id)},
            )
            db.add(audit)
            await db.commit()

            logger.info("sync_pipeline_complete", project_id=str(project_id))

        except Exception as exc:
            logger.exception("sync_pipeline_error", project_id=str(project_id), error=str(exc))
            try:
                job = await db.get(GenerationJob, job_id)
                project = await db.get(ReelProject, project_id)
                if job:
                    job.status = JobStatus.FAILED
                    job.error_message = str(exc)
                if project:
                    project.status = ReelProjectStatus.FAILED_SCRIPT
                await db.commit()
            except Exception:
                logger.exception("sync_pipeline_cleanup_error")


# ── Regenerate ────────────────────────────────────────────────────────────────

async def regenerate_reel_project(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> tuple[ReelVersion, GenerationJob]:
    """Create a new version + job and enqueue/run mock generation."""
    project = await get_project_by_id(db, user_id, project_id)

    # Count existing versions
    stmt = select(ReelVersion).where(ReelVersion.project_id == project_id)
    existing = list((await db.execute(stmt)).scalars().all())
    new_version_number = len(existing) + 1

    version = ReelVersion(
        project_id=project.id,
        version_number=new_version_number,
        status=ReelProjectStatus.DRAFT,
    )
    db.add(version)
    await db.flush()

    project.latest_version_id = version.id
    project.status = ReelProjectStatus.DRAFT

    job = GenerationJob(
        project_id=project.id,
        version_id=version.id,
        job_type="mock_generation",
        status=JobStatus.QUEUED,
        input_payload={"regenerate": True, "version_number": new_version_number},
    )
    db.add(job)
    await db.flush()

    audit = AuditLog(
        action="reel_project_regenerated",
        workspace_id=project.workspace_id,
        user_id=user_id,
        resource_type="reel_project",
        resource_id=project.id,
        metadata_={"new_version": new_version_number},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(version)
    await db.refresh(job)

    mode = settings.GENERATION_MODE
    if mode == "sync":
        await _run_mock_pipeline_inline(
            project_id=project.id,
            version_id=version.id,
            job_id=job.id,
            prompt=project.prompt,
            tone=project.tone,
            duration=project.duration_seconds,
            cta=project.cta_text,
        )
        await db.refresh(version)
        await db.refresh(job)
    else:
        try:
            from app.workers.celery_client import celery_client
            celery_client.send_task(
                "app.tasks.generate_reel.generate_reel_mock_task",
                args=[str(project.id), str(version.id), str(job.id)],
                queue="generation",
            )
        except Exception as e:
            logger.warning("celery_enqueue_failed_regenerate", error=str(e))

    return version, job


# ── Read ──────────────────────────────────────────────────────────────────────

async def get_projects(db: AsyncSession, user_id: uuid.UUID) -> list[ReelProject]:
    """List all reel projects accessible to the user (via workspace membership)."""
    stmt = (
        select(ReelProject)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == ReelProject.workspace_id)
        .where(WorkspaceMember.user_id == user_id)
        .order_by(ReelProject.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_project_by_id(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> ReelProject:
    """Fetch a single project, ensuring the user has workspace access."""
    stmt = (
        select(ReelProject)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == ReelProject.workspace_id)
        .where(
            WorkspaceMember.user_id == user_id,
            ReelProject.id == project_id,
        )
    )
    project = (await db.execute(stmt)).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def get_project_with_version(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> dict[str, Any]:
    """Fetch project + latest version for the detail page."""
    project = await get_project_by_id(db, user_id, project_id)

    latest_version = None
    if project.latest_version_id:
        latest_version = await db.get(ReelVersion, project.latest_version_id)

    return {"project": project, "latest_version": latest_version}


async def get_project_jobs(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> list[GenerationJob]:
    """Return all generation jobs for a project (ownership-checked)."""
    await get_project_by_id(db, user_id, project_id)  # Auth check
    stmt = (
        select(GenerationJob)
        .where(GenerationJob.project_id == project_id)
        .order_by(GenerationJob.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())
