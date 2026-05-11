"""
Reel project service — create, list, retrieve, and enqueue mock generation.
"""

import uuid
from pathlib import Path
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
    MediaAsset,
    MediaAssetStatus,
    MediaAssetType,
    ReelProject,
    ReelProjectStatus,
    ReelVersion,
    UsageEventType,
    WorkspaceMember,
)
from app.schemas.schemas import CreateReelProjectRequest
from app.services.ai.base import TTSProvider
from app.services.usage_service import consume_usage

logger = structlog.get_logger(__name__)


def _raise_provider_setup_error() -> None:
    from app.services.ai.provider_factory import validate_provider_configuration
    from app.services.ai.schemas import AIProviderConfigurationError

    try:
        validate_provider_configuration()
    except AIProviderConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


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
    _raise_provider_setup_error()

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
        job_type="ai_generation",
        status=JobStatus.QUEUED,
        input_payload=data.model_dump(mode="json"),
    )
    db.add(job)
    await db.flush()

    await consume_usage(
        db=db,
        workspace_id=workspace_id,
        user_id=user_id,
        event_type=UsageEventType.AI_GENERATION,
        quantity=1,
        related_project_id=project.id,
        related_version_id=version.id,
        related_job_id=str(job.id),
    )

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
        # Run provider pipeline synchronously within the API process
        await _run_provider_pipeline_inline(
            project_id=project.id,
            version_id=version.id,
            job_id=job.id,
        )
        # Refresh to pick up updated status after inline execution
        await db.refresh(project)
        await db.refresh(version)
        await db.refresh(job)
    else:
        try:
            from app.workers.celery_client import celery_client
            celery_client.send_task(
                "app.tasks.generate_reel.generate_reel_task",
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

async def _resolve_source_image_path(
    db: AsyncSession,
    project: ReelProject,
) -> Path | None:
    """Resolve the local source image path when one is available."""
    if not project.source_image_id:
        return None
    asset = await db.get(MediaAsset, project.source_image_id)
    if not asset or asset.workspace_id != project.workspace_id:
        return None
    from app.services.render_service import get_local_storage_path

    local_path = get_local_storage_path(asset)
    if local_path and local_path.exists():
        return local_path
    return None


async def _generate_voiceover_asset(
    db: AsyncSession,
    project: ReelProject,
    version: ReelVersion,
    text: str,
    provider: TTSProvider,
    provider_name: str,
) -> tuple[MediaAsset, float]:
    """Generate voiceover audio and persist it as a MediaAsset."""
    voiceovers_dir = Path(settings.LOCAL_STORAGE_PATH) / "voiceovers"
    voiceovers_dir.mkdir(parents=True, exist_ok=True)
    extension = "mp3" if provider_name == "openai" else "wav"
    filename = f"voiceover_{version.id}.{extension}"
    output_path = voiceovers_dir / filename
    result = await provider.generate_voiceover(
        text=text,
        voice=settings.TTS_VOICE or None,
        output_path=str(output_path),
    )
    file_size = output_path.stat().st_size if output_path.exists() else 0
    asset = MediaAsset(
        workspace_id=project.workspace_id,
        project_id=project.id,
        version_id=version.id,
        asset_type=MediaAssetType.AUDIO,
        s3_key=f"voiceovers/{filename}",
        s3_bucket="local",
        filename=filename,
        mime_type="audio/mpeg" if result.format == "mp3" else "audio/wav",
        file_size=file_size,
        status=MediaAssetStatus.READY if file_size > 0 else MediaAssetStatus.ERROR,
        metadata_={
            "storage_provider": "local",
            "provider": result.provider,
            "duration_seconds": result.duration_seconds,
            "format": result.format,
        },
    )
    db.add(asset)
    await db.flush()
    result.audio_asset_id = str(asset.id)
    return asset, result.duration_seconds


async def _run_provider_pipeline_inline(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    job_id: uuid.UUID,
) -> bool:
    """Run the provider-backed generation pipeline inline."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        return await _run_provider_pipeline_with_db(db, project_id, version_id, job_id)


async def _run_provider_pipeline_with_db(
    db: AsyncSession,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    job_id: uuid.UUID,
) -> bool:
    """Run the provider-backed generation pipeline using the provided DB session."""
    from datetime import UTC, datetime

    from app.services.ai.openai_provider import sanitize_provider_error
    from app.services.ai.provider_factory import get_provider_bundle
    from app.services.ai.schemas import (
        AIProviderRuntimeError,
        ReelPlanInput,
        align_subtitle_lines,
    )

    bundle = None
    try:
        job = await db.get(GenerationJob, job_id)
        project = await db.get(ReelProject, project_id)
        version = await db.get(ReelVersion, version_id)

        if not job or not project or not version:
            logger.error(
                "provider_pipeline_missing_records",
                project_id=str(project_id),
                version_id=str(version_id),
                job_id=str(job_id),
            )
            return False

        if job.status == JobStatus.COMPLETE:
            logger.info("provider_pipeline_already_complete", job_id=str(job_id))
            return True

        bundle = get_provider_bundle()
        warnings: list[str] = []

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        job.provider = bundle.ai_provider
        project.status = ReelProjectStatus.SCRIPT_GENERATING
        await db.commit()

        source_image_path = await _resolve_source_image_path(db, project)
        image_analysis = await bundle.image_analysis.analyze_image(
            str(source_image_path) if source_image_path else None
        )

        plan = await bundle.creative_planner.generate_reel_plan(
            ReelPlanInput(
                prompt=project.prompt,
                image_analysis=image_analysis,
                language=project.language,
                tone=project.tone,
                duration_seconds=project.duration_seconds,
                cta_text=project.cta_text,
            )
        )

        voiceover_asset = None
        tts_status = "missing"
        tts_error = None
        tts_duration = None
        if plan.voiceover_text:
            try:
                voiceover_asset, tts_duration = await _generate_voiceover_asset(
                    db=db,
                    project=project,
                    version=version,
                    text=plan.voiceover_text,
                    provider=bundle.tts,
                    provider_name=bundle.tts_provider,
                )
                tts_status = "generated"
                plan.subtitle_lines = align_subtitle_lines(
                    plan.subtitle_lines,
                    float(tts_duration),
                )
            except Exception as exc:
                tts_error = sanitize_provider_error(exc)
                if settings.APP_ENV == "production" and bundle.tts_provider == "openai":
                    raise AIProviderRuntimeError(tts_error, code="TTS_FAILED") from exc
                warnings.append(tts_error)
                tts_status = "failed"

        provider_metadata = {
            "ai_provider": bundle.ai_provider,
            "image_analysis_provider": bundle.image_analysis_provider,
            "tts_provider": bundle.tts_provider,
            "image_analysis": image_analysis.model_dump(mode="json"),
            "tts": {
                "status": tts_status,
                "asset_id": str(voiceover_asset.id) if voiceover_asset else None,
                "duration_seconds": tts_duration,
                "error": tts_error,
            },
            "warnings": warnings,
            "usage_note": (
                "AI_GENERATION includes planning, image analysis, subtitles, "
                "and TTS in Phase 1."
            ),
        }

        version.hook = plan.hook
        version.script = plan.script
        version.scenes = [scene.model_dump(mode="json") for scene in plan.scenes]
        version.voiceover_text = plan.voiceover_text
        version.subtitle_lines = [
            subtitle.model_dump(mode="json") for subtitle in plan.subtitle_lines
        ]
        version.caption = plan.caption
        version.hashtags = plan.hashtags
        version.video_prompt = plan.video_prompt
        version.estimated_duration = plan.estimated_duration_seconds
        version.moderation_flags = plan.moderation_flags.model_dump(mode="json")
        version.voiceover_asset_id = voiceover_asset.id if voiceover_asset else None
        version.audio_asset_id = voiceover_asset.id if voiceover_asset else version.audio_asset_id
        version.edit_metadata = {
            **(version.edit_metadata or {}),
            "ai_provider": bundle.ai_provider,
            "tts_provider": bundle.tts_provider,
            "image_analysis": image_analysis.model_dump(mode="json"),
            "voiceover_status": tts_status,
            "generation_warnings": warnings,
        }
        version.status = ReelProjectStatus.READY_FOR_REVIEW

        job.status = JobStatus.COMPLETE
        job.completed_at = datetime.now(UTC)
        job.output_payload = {
            "creative_plan": plan.model_dump(mode="json"),
            **provider_metadata,
        }
        job.provider_metadata_json = provider_metadata
        job.error_code = None

        project.status = ReelProjectStatus.READY_FOR_REVIEW

        audit = AuditLog(
            action="reel_generation_completed",
            workspace_id=project.workspace_id,
            user_id=project.created_by,
            resource_type="generation_job",
            resource_id=job.id,
            metadata_={
                "version_id": str(version_id),
                "provider": bundle.ai_provider,
                "tts_status": tts_status,
                "mode": "sync",
            },
        )
        db.add(audit)
        await db.commit()

        logger.info(
            "provider_pipeline_complete",
            project_id=str(project_id),
            version_id=str(version_id),
            job_id=str(job_id),
            provider=bundle.ai_provider,
            tts_status=tts_status,
        )
        return True

    except Exception as exc:
        safe_error = sanitize_provider_error(exc)
        error_code = getattr(exc, "code", "AI_PROVIDER_ERROR")
        provider = getattr(bundle, "ai_provider", settings.AI_PROVIDER)
        logger.exception(
            "provider_pipeline_error",
            project_id=str(project_id),
            version_id=str(version_id),
            job_id=str(job_id),
            provider=provider,
            error_type=type(exc).__name__,
            error=safe_error,
        )
        try:
            await db.rollback()
            job = await db.get(GenerationJob, job_id)
            project = await db.get(ReelProject, project_id)
            version = await db.get(ReelVersion, version_id)
            if job:
                job.status = JobStatus.FAILED
                job.provider = provider
                job.error_message = safe_error
                job.error_code = error_code
                job.completed_at = datetime.now(UTC)
                job.provider_metadata_json = {
                    "provider": provider,
                    "error_code": error_code,
                    "error_type": type(exc).__name__,
                    "error_message": safe_error,
                }
            if project:
                project.status = ReelProjectStatus.FAILED_SCRIPT
            if version:
                version.status = ReelProjectStatus.FAILED_SCRIPT
                version.edit_metadata = {
                    **(version.edit_metadata or {}),
                    "provider_error": safe_error,
                    "provider_error_code": error_code,
                }
            await db.commit()
        except Exception:
            logger.exception("provider_pipeline_cleanup_error", job_id=str(job_id))
        return False


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
    _raise_provider_setup_error()

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
        job_type="ai_generation",
        status=JobStatus.QUEUED,
        input_payload={"regenerate": True, "version_number": new_version_number},
    )
    db.add(job)
    await db.flush()

    await consume_usage(
        db=db,
        workspace_id=project.workspace_id,
        user_id=user_id,
        event_type=UsageEventType.AI_GENERATION,
        quantity=1,
        related_project_id=project.id,
        related_version_id=version.id,
        related_job_id=str(job.id),
    )

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
        await _run_provider_pipeline_inline(
            project_id=project.id,
            version_id=version.id,
            job_id=job.id,
        )
        await db.refresh(version)
        await db.refresh(job)
    else:
        try:
            from app.workers.celery_client import celery_client
            celery_client.send_task(
                "app.tasks.generate_reel.generate_reel_task",
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
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
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
    media_assets: dict[str, MediaAsset | None] = {
        "rendered_video": None,
        "thumbnail": None,
        "voiceover_audio": None,
    }
    if project.latest_version_id:
        latest_version = await db.get(ReelVersion, project.latest_version_id)
        if latest_version:
            media_assets = await get_reel_version_media_assets(db, latest_version)

    return {
        "project": project,
        "latest_version": latest_version,
        "media_assets": media_assets,
    }


async def _get_version_asset_by_id(
    db: AsyncSession,
    version: ReelVersion,
    asset_id: uuid.UUID | None,
    asset_type: MediaAssetType,
) -> MediaAsset | None:
    if not asset_id:
        return None
    asset = await db.get(MediaAsset, asset_id)
    if (
        asset
        and asset.project_id == version.project_id
        and asset.version_id == version.id
        and asset.asset_type == asset_type
        and asset.status == MediaAssetStatus.READY
    ):
        return asset
    return None


async def _get_latest_version_asset(
    db: AsyncSession,
    version: ReelVersion,
    asset_type: MediaAssetType,
) -> MediaAsset | None:
    stmt = (
        select(MediaAsset)
        .where(
            MediaAsset.project_id == version.project_id,
            MediaAsset.version_id == version.id,
            MediaAsset.asset_type == asset_type,
            MediaAsset.status == MediaAssetStatus.READY,
        )
        .order_by(MediaAsset.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().first()


async def get_reel_version_media_assets(
    db: AsyncSession,
    version: ReelVersion,
) -> dict[str, MediaAsset | None]:
    """Return safe media assets for a version, falling back to latest typed assets."""
    rendered_video = (
        await _get_version_asset_by_id(
            db,
            version,
            version.video_asset_id,
            MediaAssetType.RENDERED_VIDEO,
        )
        or await _get_version_asset_by_id(
            db,
            version,
            version.rendered_asset_id,
            MediaAssetType.RENDERED_VIDEO,
        )
        or await _get_latest_version_asset(db, version, MediaAssetType.RENDERED_VIDEO)
    )
    thumbnail = (
        await _get_version_asset_by_id(
            db,
            version,
            version.thumbnail_asset_id,
            MediaAssetType.THUMBNAIL,
        )
        or await _get_latest_version_asset(db, version, MediaAssetType.THUMBNAIL)
    )
    voiceover_audio = (
        await _get_version_asset_by_id(
            db,
            version,
            version.voiceover_asset_id,
            MediaAssetType.AUDIO,
        )
        or await _get_version_asset_by_id(
            db,
            version,
            version.audio_asset_id,
            MediaAssetType.AUDIO,
        )
        or await _get_latest_version_asset(db, version, MediaAssetType.AUDIO)
    )
    return {
        "rendered_video": rendered_video,
        "thumbnail": thumbnail,
        "voiceover_audio": voiceover_audio,
    }


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
