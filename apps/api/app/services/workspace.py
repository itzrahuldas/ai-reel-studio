import uuid

import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Workspace, WorkspaceMember
from app.schemas.schemas import CreateWorkspaceRequest, WorkspaceMemberResponse

logger = structlog.get_logger(__name__)

async def get_user_workspaces(db: AsyncSession, user_id: uuid.UUID) -> list[Workspace]:
    stmt = select(Workspace).join(WorkspaceMember).where(WorkspaceMember.user_id == user_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_workspace_by_id(db: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID) -> Workspace:
    # Ensure user is a member
    member_stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id
    )
    result = await db.execute(member_stmt)
    member = result.scalars().first()
    if not member:
        raise HTTPException(status_code=403, detail="Not authorized to access this workspace")

    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace

async def create_workspace(db: AsyncSession, user_id: uuid.UUID, data: CreateWorkspaceRequest) -> Workspace:
    # Check if slug exists
    stmt = select(Workspace).where(Workspace.slug == data.slug)
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Workspace slug already taken")

    workspace = Workspace(
        name=data.name,
        slug=data.slug,
        plan="free",
        is_active=True
    )
    db.add(workspace)
    await db.flush()

    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user_id,
        role="owner"
    )
    db.add(member)
    await db.commit()
    await db.refresh(workspace)
    return workspace

async def get_workspace_members(db: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID) -> list[WorkspaceMemberResponse]:
    # First check authorization using the previous function
    await get_workspace_by_id(db, workspace_id, user_id)

    stmt = select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
    result = await db.execute(stmt)
    members = result.scalars().all()
    return [WorkspaceMemberResponse.model_validate(m) for m in members]
