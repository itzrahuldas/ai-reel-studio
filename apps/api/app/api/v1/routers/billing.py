"""
Billing & Usage API router.

Endpoints:
  GET  /api/v1/billing/plans          — static plan definitions (public)
  GET  /api/v1/billing/usage          — current workspace usage summary (auth required)

  Development-only (APP_ENV=development):
  POST /api/v1/billing/dev/set-plan   — override workspace plan
  POST /api/v1/billing/dev/grant-usage — grant artificial usage (for testing limits)
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.models.models import (
    SubscriptionStatus,
    UsageEventType,
    WorkspaceSubscription,
    WorkspaceMember,
)
from app.schemas.schemas import (
    PlanDefinition,
    PlanKey,
    SetDevPlanRequest,
    GrantDevUsageRequest,
    UsageSummaryResponse,
)
from app.services.usage_service import (
    PLANS,
    consume_usage,
    get_usage_summary,
    get_workspace_plan,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Plan Definitions (public) ─────────────────────────────────────────────────

@router.get("/plans", response_model=list[PlanDefinition])
async def list_plans() -> Any:
    """
    Return all available billing plan definitions.
    This endpoint is public — no auth required.
    Useful for pricing pages and upgrade modals.
    """
    return list(PLANS.values())


# ── Usage Summary (auth required) ─────────────────────────────────────────────

@router.get("/usage", response_model=UsageSummaryResponse)
async def get_usage(
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """
    Return current usage summary for the authenticated user's workspace.

    Response includes:
    - Current plan definition with all limits
    - Current period start/end
    - Usage counts for AI generations, renders, publishes, and scheduled publishes
    - Watermark setting for the plan

    Use this to drive usage bars and upgrade CTAs in the frontend.
    """
    from sqlalchemy import select

    # Resolve workspace_id for the current user
    stmt = select(WorkspaceMember.workspace_id).where(
        WorkspaceMember.user_id == current_user.id
    )
    result = await db.execute(stmt)
    workspace_id = result.scalars().first()
    if not workspace_id:
        raise HTTPException(
            status_code=400,
            detail="User has no workspace. Please complete onboarding.",
        )

    return await get_usage_summary(db, workspace_id)


# ── Dev Routes (development only) ─────────────────────────────────────────────

def _require_dev_env() -> None:
    """Dependency that rejects requests unless APP_ENV=development."""
    if settings.APP_ENV != "development":
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only available in development mode.",
        )


DevEnv = Depends(_require_dev_env)


@router.post(
    "/dev/set-plan",
    status_code=200,
    dependencies=[DevEnv],
)
async def dev_set_plan(
    data: SetDevPlanRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """
    **DEV ONLY** — Override the workspace plan for testing.

    Sets the active subscription's plan_key to the given value.
    If no subscription exists, creates one with ACTIVE status.

    Available plan keys: FREE | CREATOR | PRO
    """
    from sqlalchemy import select

    stmt = select(WorkspaceMember.workspace_id).where(
        WorkspaceMember.user_id == current_user.id
    )
    result = await db.execute(stmt)
    workspace_id = result.scalars().first()
    if not workspace_id:
        raise HTTPException(status_code=400, detail="User has no workspace")

    now = datetime.now(UTC)
    # Find or create workspace subscription
    sub_stmt = select(WorkspaceSubscription).where(
        WorkspaceSubscription.workspace_id == workspace_id
    )
    sub_result = await db.execute(sub_stmt)
    subscription = sub_result.scalar_one_or_none()

    if subscription:
        subscription.plan_key = data.plan_key.value
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.updated_at = now
    else:
        # Calculate current month period
        period_start = datetime(now.year, now.month, 1, tzinfo=UTC)
        if now.month == 12:
            period_end = datetime(now.year + 1, 1, 1, tzinfo=UTC)
        else:
            period_end = datetime(now.year, now.month + 1, 1, tzinfo=UTC)

        subscription = WorkspaceSubscription(
            workspace_id=workspace_id,
            plan_key=data.plan_key.value,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=period_start,
            current_period_end=period_end,
            cancel_at_period_end=False,
        )
        db.add(subscription)

    await db.commit()

    logger.info(
        "dev_plan_set",
        workspace_id=str(workspace_id),
        plan_key=data.plan_key.value,
    )

    plan = PLANS[data.plan_key]
    return {
        "message": f"Plan set to {data.plan_key.value}",
        "plan": plan.model_dump(),
        "workspace_id": str(workspace_id),
    }


@router.post(
    "/dev/grant-usage",
    status_code=200,
    dependencies=[DevEnv],
)
async def dev_grant_usage(
    data: GrantDevUsageRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> Any:
    """
    **DEV ONLY** — Artificially increment usage counters for testing limit enforcement.

    Example: Grant 10 AI_GENERATION events to test the 402 limit response.
    This bypasses limit checks and directly increments counters + logs events.

    event_type: AI_GENERATION | RENDER | PUBLISH | SCHEDULED_PUBLISH
    """
    from sqlalchemy import select
    from app.services.usage_service import get_or_create_current_usage_counter
    from app.models.models import UsageEvent

    stmt = select(WorkspaceMember.workspace_id).where(
        WorkspaceMember.user_id == current_user.id
    )
    result = await db.execute(stmt)
    workspace_id = result.scalars().first()
    if not workspace_id:
        raise HTTPException(status_code=400, detail="User has no workspace")

    # Validate event_type string
    try:
        event_type = UsageEventType(data.event_type)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid event_type '{data.event_type}'. "
                   "Must be one of: AI_GENERATION, RENDER, PUBLISH, SCHEDULED_PUBLISH",
        )

    # Add usage event records (bypass limit check)
    for _ in range(data.quantity):
        event = UsageEvent(
            workspace_id=workspace_id,
            user_id=current_user.id,
            event_type=event_type,
            quantity=1,
            metadata_json={"source": "dev_grant_usage"},
        )
        db.add(event)

    # Increment counter
    counter = await get_or_create_current_usage_counter(db, workspace_id)
    if event_type == UsageEventType.AI_GENERATION:
        counter.ai_generations_used += data.quantity
    elif event_type == UsageEventType.RENDER:
        counter.renders_used += data.quantity
    elif event_type == UsageEventType.PUBLISH:
        counter.publishes_used += data.quantity
    elif event_type == UsageEventType.SCHEDULED_PUBLISH:
        counter.scheduled_publishes_created += data.quantity

    await db.commit()

    logger.info(
        "dev_usage_granted",
        workspace_id=str(workspace_id),
        event_type=data.event_type,
        quantity=data.quantity,
    )

    return {
        "message": f"Granted {data.quantity} × {data.event_type} usage events",
        "workspace_id": str(workspace_id),
        "event_type": data.event_type,
        "quantity": data.quantity,
    }
