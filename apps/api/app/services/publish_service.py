"""
Service for managing Reel publishing jobs to social platforms.
"""

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import decrypt_token
from app.models.models import (
    AuditLog,
    MediaAsset,
    PublishJob,
    PublishJobStatus,
    ReelProject,
    ReelProjectStatus,
    ReelVersion,
    SocialAccount,
    SocialAccountStatus,
    UsageEventType,
    WorkspaceMember,
)
from app.schemas.schemas import CreatePublishJobRequest, SchedulePublishJobRequest
from app.services.usage_service import check_usage_limit, consume_usage

logger = structlog.get_logger(__name__)


def build_public_media_url(asset: MediaAsset) -> str:
    """
    Return a publicly accessible HTTPS URL for a media asset.
    In live mode, it MUST be public HTTPS.
    In mock mode, local URLs or localhost are allowed.
    """
    asset_url = getattr(asset, "url", None)
    if asset_url:
        # If it's an external URL (e.g. S3), use it directly
        if settings.INSTAGRAM_INTEGRATION_MODE == "live" and not asset_url.startswith("https://"):
            raise HTTPException(
                status_code=400,
                detail="Live Instagram publishing requires a public HTTPS video URL.",
            )
        return asset_url

    # If storage is local, we must use STORAGE_PUBLIC_BASE_URL or API_PUBLIC_BASE_URL
    base = settings.STORAGE_PUBLIC_BASE_URL or settings.API_PUBLIC_BASE_URL
    if not base:
        base = "http://localhost:8000"

    url = f"{base.rstrip('/')}/api/v1/media-assets/{asset.id}/download"

    if (
        settings.INSTAGRAM_INTEGRATION_MODE == "live"
        and (not url.startswith("https://") or "localhost" in url or "127.0.0.1" in url)
    ):
        raise HTTPException(
            status_code=400,
            detail="Live Instagram publishing requires a public HTTPS video URL. "
            "Use deployed storage or a tunnel for development.",
        )

    return url


async def validate_publish_preflight(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    social_account_id: uuid.UUID,
) -> tuple[ReelProject, ReelVersion, SocialAccount, MediaAsset]:
    """
    Validate that the project and social account are ready for publishing.
    """
    # 1. Load Project
    stmt = (
        select(ReelProject)
        .where(ReelProject.id == project_id)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == ReelProject.workspace_id)
        .where(WorkspaceMember.user_id == user_id)
    )
    project = (await db.execute(stmt)).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.latest_version_id:
        raise HTTPException(status_code=400, detail="Project has no version to publish")

    # 2. Load Version
    version_stmt = select(ReelVersion).where(ReelVersion.id == project.latest_version_id)
    version = (await db.execute(version_stmt)).scalars().first()
    if not version or not version.video_asset_id:
        raise HTTPException(status_code=400, detail="No rendered video available for publishing")

    # 3. Load Media Asset
    asset_stmt = select(MediaAsset).where(MediaAsset.id == version.video_asset_id)
    asset = (await db.execute(asset_stmt)).scalars().first()
    if not asset:
        raise HTTPException(status_code=400, detail="Video asset missing")

    if asset.mime_type != "video/mp4":
        raise HTTPException(status_code=400, detail="Rendered video must be MP4 for Instagram")

    # 4. Load Social Account
    social_stmt = select(SocialAccount).where(
        SocialAccount.id == social_account_id,
        SocialAccount.workspace_id == project.workspace_id
    )
    social_account = (await db.execute(social_stmt)).scalars().first()
    if not social_account:
        raise HTTPException(status_code=404, detail="Social account not found or access denied")

    if social_account.status != SocialAccountStatus.CONNECTED:
        raise HTTPException(status_code=400, detail="Social account is not connected")

    if not social_account.ig_user_id:
        raise HTTPException(status_code=400, detail="Social account missing Instagram user ID")

    # Check token expiry if provided
    if settings.INSTAGRAM_INTEGRATION_MODE == "live":
        if social_account.token_expires_at and social_account.token_expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=400,
                detail="Instagram access token expired. Reconnect required.",
            )
        if not social_account.access_token_encrypted:
            raise HTTPException(
                status_code=400,
                detail="Instagram access token missing. Reconnect required.",
            )
        try:
            decrypt_token(social_account.access_token_encrypted)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="Instagram access token could not be decrypted. Reconnect required.",
            ) from exc

    # 5. Check duplicate publish
    existing_job_stmt = select(PublishJob).where(
        PublishJob.project_id == project_id,
        PublishJob.status.in_(
            [
                PublishJobStatus.SCHEDULED,
                PublishJobStatus.QUEUED,
                PublishJobStatus.POLLING,
                PublishJobStatus.CONTAINER_CREATED,
            ]
        ),
    )
    existing_job = (await db.execute(existing_job_stmt)).scalars().first()
    if existing_job:
        raise HTTPException(status_code=400, detail="Project is already being published")

    return project, version, social_account, asset


async def create_publish_job(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    data: CreatePublishJobRequest,
) -> tuple[PublishJob, ReelProject, ReelVersion]:
    """
    Create a new publish job and enqueue it immediately.
    data is schemas.CreatePublishJobRequest.
    """
    project, version, social_account, asset = await validate_publish_preflight(
        db, user_id, project_id, data.social_account_id
    )

    # Use caption from request, fallback to version.caption
    caption = data.caption if data.caption is not None else version.caption
    if not caption:
        caption = ""

    # Include hashtags if we fallback to version caption
    if data.caption is None and version.hashtags:
        caption += "\n\n" + " ".join(f"#{tag}" for tag in version.hashtags)

    # In live mode, validate URL before billing usage is consumed.
    video_url = build_public_media_url(asset)

    job = PublishJob(
        project_id=project.id,
        version_id=version.id,
        social_account_id=social_account.id,
        status=PublishJobStatus.QUEUED,
        # additional fields can be mapped into input_payload for now
        input_payload={
            "caption": caption,
            "share_to_feed": data.share_to_feed,
            "allow_comments": data.allow_comments,
            "video_url": video_url,
        }
    )
    db.add(job)
    await db.flush()

    await consume_usage(
        db=db,
        workspace_id=project.workspace_id,
        user_id=user_id,
        event_type=UsageEventType.PUBLISH,
        quantity=1,
        related_project_id=project.id,
        related_version_id=version.id,
        related_job_id=str(job.id),
    )

    project.status = ReelProjectStatus.PUBLISHING
    version.status = ReelProjectStatus.PUBLISHING

    log = AuditLog(
        workspace_id=project.workspace_id,
        user_id=user_id,
        action="publish_job_created",
        resource_type="reel_project",
        resource_id=project.id,
        metadata_={"job_id": str(job.id), "social_account_id": str(social_account.id)},
    )
    db.add(log)

    await db.commit()
    await db.refresh(job)

    # Enqueue or run inline
    if settings.PUBLISH_MODE == "async":
        try:
            from app.workers.celery_client import celery_client
            task = celery_client.send_task(
                "app.tasks.publish_reel.publish_reel_task",
                args=[str(job.id)],
                queue="publishing",
            )
            job.celery_task_id = str(task.id)
            await db.commit()
            await db.refresh(job)
        except Exception as e:
            logger.warning("celery_publish_enqueue_failed", error=str(e))
    else:
        # Sync mode — run publish pipeline inline in a background task
        import asyncio

        from app.services._publish_pipeline import run_publish_pipeline_inline
        asyncio.create_task(run_publish_pipeline_inline(str(job.id)))

    return job, project, version


async def get_publish_jobs(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> list[PublishJob]:
    """Return publish jobs for a project."""
    stmt = (
        select(PublishJob)
        .join(ReelProject, ReelProject.id == PublishJob.project_id)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == ReelProject.workspace_id)
        .where(WorkspaceMember.user_id == user_id, PublishJob.project_id == project_id)
        .order_by(PublishJob.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def retry_publish_job(db: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID) -> PublishJob:
    """Retry a failed publish job."""
    stmt = (
        select(PublishJob)
        .where(PublishJob.id == job_id)
        .join(ReelProject, ReelProject.id == PublishJob.project_id)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == ReelProject.workspace_id)
        .where(WorkspaceMember.user_id == user_id)
        .options(selectinload(PublishJob.project))
    )
    job = (await db.execute(stmt)).scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Publish job not found")

    if job.status not in [PublishJobStatus.FAILED, PublishJobStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail="Only failed or cancelled jobs can be retried")

    # Reset status
    job.status = PublishJobStatus.QUEUED
    job.error_message = None
    job.retry_count += 1
    job.started_at = None
    job.completed_at = None
    job.published_at = None

    project = job.project
    project.status = ReelProjectStatus.PUBLISHING

    await db.commit()

    if settings.PUBLISH_MODE == "async":
        try:
            from app.workers.celery_client import celery_client
            task = celery_client.send_task(
                "app.tasks.publish_reel.publish_reel_task",
                args=[str(job.id)],
                queue="publishing",
            )
            job.celery_task_id = str(task.id)
            await db.commit()
        except Exception as e:
            logger.warning("celery_publish_retry_enqueue_failed", error=str(e))
    else:
        import asyncio

        from app.services._publish_pipeline import run_publish_pipeline_inline
        asyncio.create_task(run_publish_pipeline_inline(str(job.id)))

    return job

async def schedule_publish_job(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    data: SchedulePublishJobRequest,
) -> tuple[PublishJob, ReelProject, ReelVersion]:
    """
    Schedule a publish job for a future time.
    """
    from datetime import timedelta

    project, version, social_account, asset = await validate_publish_preflight(
        db, user_id, project_id, data.social_account_id
    )

    now = datetime.now(UTC)
    if data.scheduled_at < now + timedelta(minutes=2):
        raise HTTPException(
            status_code=400,
            detail="Scheduled time must be at least 2 minutes in the future",
        )

    if data.scheduled_at > now + timedelta(days=90):
        raise HTTPException(
            status_code=400,
            detail="Scheduled time cannot be more than 90 days in the future",
        )

    caption = data.caption if data.caption is not None else version.caption
    if not caption:
        caption = ""

    if data.caption is None and version.hashtags:
        caption += "\n\n" + " ".join(f"#{tag}" for tag in version.hashtags)

    video_url = build_public_media_url(asset)
    await check_usage_limit(
        db=db,
        workspace_id=project.workspace_id,
        event_type=UsageEventType.SCHEDULED_PUBLISH,
        throw_if_exceeded=True,
        quantity=1,
    )

    job = PublishJob(
        project_id=project.id,
        version_id=version.id,
        social_account_id=social_account.id,
        status=PublishJobStatus.SCHEDULED,
        scheduled_for=data.scheduled_at,
        schedule_timezone=data.schedule_timezone,
        input_payload={
            "caption": caption,
            "share_to_feed": data.share_to_feed,
            "allow_comments": data.allow_comments,
            "video_url": video_url,
        }
    )
    db.add(job)
    await db.flush()

    await consume_usage(
        db=db,
        workspace_id=project.workspace_id,
        user_id=user_id,
        event_type=UsageEventType.SCHEDULED_PUBLISH,
        quantity=1,
        related_project_id=project.id,
        related_version_id=version.id,
        related_job_id=str(job.id),
        metadata_json={"source": "schedule_created"},
        enforce_limit=False,
    )

    log = AuditLog(
        workspace_id=project.workspace_id,
        user_id=user_id,
        action="publish_job_scheduled",
        resource_type="reel_project",
        resource_id=project.id,
        metadata_={
            "job_id": str(job.id),
            "social_account_id": str(social_account.id),
            "scheduled_for": data.scheduled_at.isoformat(),
        },
    )
    db.add(log)

    await db.commit()
    await db.refresh(job)

    return job, project, version

async def cancel_scheduled_publish_job(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> PublishJob:
    """
    Cancel a scheduled publish job.
    """
    stmt = (
        select(PublishJob)
        .where(PublishJob.id == job_id)
        .join(ReelProject, ReelProject.id == PublishJob.project_id)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == ReelProject.workspace_id)
        .where(WorkspaceMember.user_id == user_id)
    )
    job = (await db.execute(stmt)).scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Publish job not found")

    if job.status != PublishJobStatus.SCHEDULED:
        raise HTTPException(status_code=400, detail="Only scheduled jobs can be cancelled")

    job.status = PublishJobStatus.CANCELLED
    job.cancelled_at = datetime.now(UTC)
    job.cancel_reason = "Cancelled by user"

    await db.commit()

    return job
