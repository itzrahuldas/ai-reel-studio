"""
Reel Projects API router.
All routes require authenticated user. Ownership enforced via workspace membership.
"""

import uuid
from typing import Any

import structlog
from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.models.models import MediaAsset
from app.schemas.schemas import (
    AIProviderStatusResponse,
    CreatePublishJobRequest,
    CreatePublishJobResponse,
    CreateReelProjectRequest,
    CreateReelProjectResponse,
    CreateRenderJobResponse,
    GenerationJobResponse,
    PublishJobResponse,
    ReelProjectResponse,
    ReelVersionEditorResponse,
    ReelVersionResponse,
    RenderJobResponse,
    SaveEditorDraftResponse,
    SchedulePublishJobRequest,
    UpdateReelVersionRequest,
)
from app.services.ai.provider_factory import get_provider_status
from app.services.editor_service import clone_reel_version, get_editor_data, update_reel_version
from app.services.publish_service import create_publish_job, get_publish_jobs, retry_publish_job
from app.services.reel_project import (
    create_reel_project,
    get_project_jobs,
    get_project_with_version,
    get_projects,
    get_reel_version_media_assets,
    regenerate_reel_project,
)
from app.services.render_service import build_media_url, create_render_job, get_render_jobs

logger = structlog.get_logger(__name__)
router = APIRouter()


def _metadata_value(asset: MediaAsset | None, key: str) -> str | None:
    metadata = asset.metadata_ if asset and isinstance(asset.metadata_, dict) else {}
    value = metadata.get(key)
    return str(value) if value is not None else None


def _enrich_version_media(
    version: ReelVersionResponse,
    media_assets: dict[str, MediaAsset | None] | None,
) -> ReelVersionResponse:
    media_assets = media_assets or {}
    rendered_video = media_assets.get("rendered_video")
    thumbnail = media_assets.get("thumbnail")
    voiceover_audio = media_assets.get("voiceover_audio")

    if rendered_video:
        url = build_media_url(rendered_video)
        version.rendered_video_url = url
        version.rendered_video_mime_type = rendered_video.mime_type
        version.video_asset_id = version.video_asset_id or rendered_video.id
        version.rendered_asset_id = version.rendered_asset_id or rendered_video.id

    if thumbnail:
        version.thumbnail_url = build_media_url(thumbnail)
        version.thumbnail_asset_id = version.thumbnail_asset_id or thumbnail.id

    if voiceover_audio:
        url = build_media_url(voiceover_audio)
        version.audio_url = url
        version.voiceover_url = url
        version.audio_mime_type = voiceover_audio.mime_type
        version.voiceover_provider = _metadata_value(voiceover_audio, "provider")
        version.audio_asset_id = version.audio_asset_id or voiceover_audio.id
        version.voiceover_asset_id = version.voiceover_asset_id or voiceover_audio.id

    return version


@router.post("/", status_code=201, response_model=CreateReelProjectResponse)
async def create_project(
    data: CreateReelProjectRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """
    Create a new Reel Project and enqueue mock generation.

    Flow:
    1. Upload image separately via POST /api/v1/media-assets/upload → get asset_id
    2. Call this endpoint with source_image_id = asset_id
    3. Backend creates project, version placeholder, and generation job
    4. Backend enqueues Celery task (or runs sync if GENERATION_MODE=sync)
    """
    project, version, job = await create_reel_project(db, current_user.id, data)
    return {
        "project": ReelProjectResponse.model_validate(project),
        "version": ReelVersionResponse.model_validate(version),
        "generation_job": GenerationJobResponse.model_validate(job),
    }


@router.get("/", response_model=list[ReelProjectResponse])
async def list_projects(current_user: CurrentUser, db: DbSession) -> Any:
    """List all Reel projects belonging to the user's workspaces."""
    projects = await get_projects(db, current_user.id)
    return [ReelProjectResponse.model_validate(p) for p in projects]


@router.get("/ai/provider-status", response_model=AIProviderStatusResponse)
async def get_ai_provider_status(_current_user: CurrentUser) -> AIProviderStatusResponse:
    """Return safe AI provider mode/configuration status for UI warnings."""
    return AIProviderStatusResponse.model_validate(get_provider_status())


@router.get("/{project_id}")
async def get_project(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """
    Get full project detail including latest version content.
    Returns project metadata + generated hook/script/storyboard/caption/hashtags.
    """
    data = await get_project_with_version(db, current_user.id, project_id)
    project = data["project"]
    latest_version = data["latest_version"]
    media_assets = data.get("media_assets")

    resp = ReelProjectResponse.model_validate(project)
    if latest_version:
        resp.latest_version = _enrich_version_media(
            ReelVersionResponse.model_validate(latest_version),
            media_assets,
        )

    return resp


@router.post("/{project_id}/regenerate", status_code=201)
async def regenerate_project(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """
    Create a new generation version + job and enqueue mock regeneration.
    Returns the new version and job.
    """
    version, job = await regenerate_reel_project(db, current_user.id, project_id)
    return {
        "version": ReelVersionResponse.model_validate(version),
        "generation_job": GenerationJobResponse.model_validate(job),
    }


@router.get("/{project_id}/jobs", response_model=list[GenerationJobResponse])
async def get_jobs(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """Return generation timeline / jobs for the project."""
    jobs = await get_project_jobs(db, current_user.id, project_id)
    return [GenerationJobResponse.model_validate(j) for j in jobs]


@router.post("/{project_id}/render", status_code=201, response_model=CreateRenderJobResponse)
async def render_project(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    version_id: uuid.UUID | None = None,
) -> Any:
    """Create a render job for the specified or latest version and enqueue FFmpeg render task."""
    render_job, project, version = await create_render_job(db, current_user.id, project_id, version_id)
    has_media_asset_ids = any(
        [
            version.video_asset_id,
            version.rendered_asset_id,
            version.thumbnail_asset_id,
            version.voiceover_asset_id,
            version.audio_asset_id,
        ]
    )
    media_assets = await get_reel_version_media_assets(db, version) if has_media_asset_ids else {}
    return {
        "render_job": RenderJobResponse.model_validate(render_job),
        "project": ReelProjectResponse.model_validate(project),
        "version": _enrich_version_media(
            ReelVersionResponse.model_validate(version),
            media_assets,
        ),
    }


@router.get("/{project_id}/render-jobs", response_model=list[RenderJobResponse])
async def list_render_jobs(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """Return render jobs for a project."""
    jobs = await get_render_jobs(db, current_user.id, project_id)
    return [RenderJobResponse.model_validate(j) for j in jobs]


# ── Editor ────────────────────────────────────────────────────────────────────


@router.get("/{project_id}/editor", response_model=ReelVersionEditorResponse)
async def get_project_editor_data(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """Return editable project/version data for the current user."""
    return await get_editor_data(db, current_user.id, project_id)

@router.put("/{project_id}/versions/{version_id}", response_model=SaveEditorDraftResponse)
async def update_project_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    data: UpdateReelVersionRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """Save edits to a version or create a safe new version depending on version state."""
    return await update_reel_version(db, current_user.id, project_id, version_id, data)

@router.post("/{project_id}/versions/{version_id}/clone", response_model=ReelVersionResponse)
async def clone_project_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """Clone a version for editing."""
    version = await clone_reel_version(db, current_user.id, project_id, version_id)
    return ReelVersionResponse.model_validate(version)


# ── Publishing ────────────────────────────────────────────────────────────────
@router.post("/{project_id}/publish", response_model=CreatePublishJobResponse)
async def publish_project(
    project_id: uuid.UUID,
    data: CreatePublishJobRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """Create a publish job for the latest version and enqueue publish task."""
    publish_job, project, version = await create_publish_job(db, current_user.id, project_id, data)
    return {
        "publish_job": PublishJobResponse.model_validate(publish_job),
        "project": ReelProjectResponse.model_validate(project),
        "version": ReelVersionResponse.model_validate(version),
    }

@router.post("/{project_id}/schedule", response_model=CreatePublishJobResponse)
async def schedule_project_publish(
    project_id: uuid.UUID,
    data: SchedulePublishJobRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """Schedule a publish job for a future time."""
    from app.services.publish_service import schedule_publish_job
    publish_job, project, version = await schedule_publish_job(db, current_user.id, project_id, data)
    return {
        "publish_job": PublishJobResponse.model_validate(publish_job),
        "project": ReelProjectResponse.model_validate(project),
        "version": ReelVersionResponse.model_validate(version),
    }

@router.delete("/publish-jobs/{publish_job_id}/schedule", response_model=PublishJobResponse)
async def cancel_scheduled_publish(
    publish_job_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """Cancel a scheduled publish job."""
    from app.services.publish_service import cancel_scheduled_publish_job
    job = await cancel_scheduled_publish_job(db, current_user.id, publish_job_id)
    return PublishJobResponse.model_validate(job)


@router.get("/{project_id}/publish-jobs", response_model=list[PublishJobResponse])
async def list_publish_jobs(
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """Return publish jobs for a project."""
    jobs = await get_publish_jobs(db, current_user.id, project_id)
    return [PublishJobResponse.model_validate(j) for j in jobs]


@router.post("/publish-jobs/{publish_job_id}/retry", response_model=PublishJobResponse)
async def retry_publish(
    publish_job_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """Retry a failed publish job."""
    job = await retry_publish_job(db, current_user.id, publish_job_id)
    return PublishJobResponse.model_validate(job)
