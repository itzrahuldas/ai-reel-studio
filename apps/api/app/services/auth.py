import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.models import (
    AuditLog,
    SubscriptionStatus,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
    WorkspacePlan,
    WorkspaceSubscription,
)
from app.schemas.schemas import AuthResponse, UserCreate, UserResponse, WorkspaceResponse

logger = structlog.get_logger(__name__)

async def create_default_workspace(db: AsyncSession, user: User) -> Workspace:
    """Create a default workspace + FREE subscription for a newly registered user."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    base_slug = f"{user.id.hex[:8]}-workspace"
    workspace = Workspace(
        name=f"{user.full_name or 'My'} Workspace",
        slug=base_slug,
        plan=WorkspacePlan.FREE,
        is_active=True,
        owner_id=user.id,
    )
    db.add(workspace)
    await db.flush()  # Get workspace.id

    member = WorkspaceMember(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceMemberRole.OWNER,
    )
    db.add(member)

    # Auto-create FREE subscription
    period_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    if now.month == 12:
        period_end = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        period_end = datetime(now.year, now.month + 1, 1, tzinfo=UTC)

    subscription = WorkspaceSubscription(
        workspace_id=workspace.id,
        plan_key="FREE",
        status=SubscriptionStatus.ACTIVE,
        provider="manual",
        current_period_start=period_start,
        current_period_end=period_end,
        cancel_at_period_end=False,
    )
    db.add(subscription)

    audit = AuditLog(
        action="workspace_created",
        workspace_id=workspace.id,
        user_id=user.id,
        resource_type="workspace",
        resource_id=workspace.id,
        metadata_={"plan": "free"},
    )
    db.add(audit)
    return workspace


async def register_user(db: AsyncSession, user_in: UserCreate) -> AuthResponse:
    """Register a new user and create their default workspace."""
    # Check duplicate email
    result = await db.execute(select(User).where(User.email == user_in.email.lower()))
    if result.scalars().first():
        logger.warning("register_duplicate_email", email=user_in.email)
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=user_in.email.lower(),
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        is_active=True,
        is_verified=False
    )
    db.add(user)
    await db.flush()

    workspace = await create_default_workspace(db, user)

    # Audit log
    audit = AuditLog(
        action="user_registered",
        workspace_id=workspace.id,
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        metadata_={}
    )
    db.add(audit)
    await db.commit()
    await db.refresh(user)
    await db.refresh(workspace)

    token = create_access_token(subject=user.id)

    logger.info("user_registered", user_id=str(user.id))
    return AuthResponse(
        user=UserResponse.model_validate(user),
        workspace=WorkspaceResponse.model_validate(workspace),
        access_token=token
    )

async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalars().first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
