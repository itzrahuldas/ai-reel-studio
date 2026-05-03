"""
Reel Projects API router.
All routes require authenticated user. Ownership enforced via workspace membership.
"""

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, DbSession
from app.schemas.schemas import (
    CreateReelProjectRequest,
    CreateReelProjectResponse,
    CreateRenderJobResponse,
    GenerationJobResponse,
    ReelProjectResponse,
    ReelVersionResponse,
    RenderJobResponse,
)
from app.services.reel_project import (
    create_reel_project,
    get_project_jobs,
    get_project_with_version,
    get_projects,
    regenerate_reel_project,
)
from app.services.render_service import create_render_job, get_render_jobs

logger = structlog.get_logger(__name__)
router = APIRouter()


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

    resp = ReelProjectResponse.model_validate(project)
    if latest_version:
        resp.latest_version = ReelVersionResponse.model_validate(latest_version)

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
) -> Any:
    """Create a render job for the latest version and enqueue FFmpeg render task."""
    render_job, project, version = await create_render_job(db, current_user.id, project_id)
    return {
        "render_job": RenderJobResponse.model_validate(render_job),
        "project": ReelProjectResponse.model_validate(project),
        "version": ReelVersionResponse.model_validate(version),
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
