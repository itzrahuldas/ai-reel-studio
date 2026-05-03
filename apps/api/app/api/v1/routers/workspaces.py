import uuid
from typing import Any

import structlog
from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.schemas import CreateWorkspaceRequest, WorkspaceMemberResponse, WorkspaceResponse
from app.services.workspace import (
    create_workspace,
    get_user_workspaces,
    get_workspace_by_id,
    get_workspace_members,
)

logger = structlog.get_logger(__name__)
router = APIRouter()

@router.get("/", response_model=list[WorkspaceResponse])
async def list_workspaces(current_user: CurrentUser, db: DbSession) -> Any:
    """List all workspaces the authenticated user belongs to."""
    return await get_user_workspaces(db, current_user.id)

@router.post("/", response_model=WorkspaceResponse, status_code=201)
async def create_new_workspace(
    data: CreateWorkspaceRequest, current_user: CurrentUser, db: DbSession
) -> Any:
    """Create a new workspace."""
    logger.info("creating_workspace", user_id=str(current_user.id), slug=data.slug)
    return await create_workspace(db, current_user.id, data)

@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Any:
    """Get a specific workspace by ID."""
    return await get_workspace_by_id(db, workspace_id, current_user.id)

@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
async def get_members(
    workspace_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Any:
    """List all members of a specific workspace."""
    return await get_workspace_members(db, workspace_id, current_user.id)
