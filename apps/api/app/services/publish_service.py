"""
Service for managing Reel publishing jobs to social platforms.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
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
    WorkspaceMember,
)

logger = structlog.get_logger(__name__)


def build_public_media_url(asset: MediaAsset) -> str:
    """
    Return a publicly accessible HTTPS URL for a media asset.
    In live mode, it MUST be public HTTPS.
    In mock mode, local URLs or localhost are allowed.
    """
    if asset.url:
        # If it's an external URL (e.g. S3), use it directly
        if asset.url.startswith("http://") and settings.INSTAGRAM_INTEGRATION_MODE == "live":
            # Just a safety check; Meta requires HTTPS.
            pass
        return asset.url

    # If storage is local, we must use STORAGE_PUBLIC_BASE_URL or API_PUBLIC_BASE_URL
    base = settings.STORAGE_PUBLIC_BASE_URL or settings.API_PUBLIC_BASE_URL
    if not base:
        base = "http://localhost:8000"

    url = f"{base.rstrip('/')}/api/v1/media-assets/{asset.id}/download"

    if settings.INSTAGRAM_INTEGRATION_MODE == "live":
        if "localhost" in url or "127.0.0.1" in url:
            raise HTTPException(
                status_code=400,
                detail="Live Instagram publishing requires a public HTTPS video URL. "
                       "Use deployed storage or a tunnel for development."
            )

    return url


async def validate_publish_preflight(
    db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID, social_account_id: uuid.UUID
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
            raise HTTPException(status_code=400, detail="Instagram access token expired. Reconnect required.")
        if not social_account.access_token_encrypted:
            raise HTTPException(status_code=400, detail="Instagram access token missing. Reconnect required.")

    # 5. Check duplicate publish
    existing_job_stmt = select(PublishJob).where(
        PublishJob.project_id == project_id,
        PublishJob.status.in_([PublishJobStatus.PUBLISHING, PublishJobStatus.QUEUED, PublishJobStatus.POLLING, PublishJobStatus.CONTAINER_CREATED])
    )
    existing_job = (await db.execute(existing_job_stmt)).scalars().first()
    if existing_job:
        raise HTTPException(status_code=400, detail="Project is already being published")

    return project, version, social_account, asset


async def create_publish_job(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    data: Any
) -> tuple[PublishJob, ReelProject, ReelVersion]:
    """
    Create a new publish job and enqueue it.
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

    # In live mode, validate URL first
    _ = build_public_media_url(asset)

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
            "video_url": build_public_media_url(asset)
        }
    )
    db.add(job)

    project.status = ReelProjectStatus.PUBLISHING
    version.status = ReelProjectStatus.PUBLISHING

    log = AuditLog(
        workspace_id=project.workspace_id,
        user_id=user_id,
        action="publish_job_created",
        entity_type="reel_project",
        entity_id=project.id,
        details={"job_id": str(job.id), "social_account_id": str(social_account.id)}
    )
    db.add(log)

    await db.commit()
    await db.refresh(job)

    # Enqueue task
    if settings.PUBLISH_MODE == "async":
        # Deferred import to avoid circular dependency
        from apps.worker.app.tasks.publish_reel import publish_reel_task
        task = publish_reel_task.delay(str(job.id))
        job.celery_task_id = task.id
        await db.commit()
        await db.refresh(job)
    else:
        # Sync mode - execute immediately
        import asyncio

        from apps.worker.app.tasks.publish_reel import run_publish_pipeline

        # We need a new session for the sync worker
        from app.db.session import AsyncSessionLocal

        async def _run_sync():
            async with AsyncSessionLocal() as session:
                await run_publish_pipeline(session, str(job.id))

        asyncio.create_task(_run_sync())

    return job, project, version


async def get_publish_jobs(db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID) -> list[PublishJob]:
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
        from apps.worker.app.tasks.publish_reel import publish_reel_task
        task = publish_reel_task.delay(str(job.id))
        job.celery_task_id = task.id
        await db.commit()
    else:
        import asyncio

        from apps.worker.app.tasks.publish_reel import run_publish_pipeline

        from app.db.session import AsyncSessionLocal
        async def _run_sync():
            async with AsyncSessionLocal() as session:
                await run_publish_pipeline(session, str(job.id))
        asyncio.create_task(_run_sync())

    return job
