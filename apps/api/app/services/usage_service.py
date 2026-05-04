import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    WorkspaceSubscription,
    UsageCounter,
    UsageEvent,
    UsageEventType,
    SubscriptionStatus,
    PublishJob,
    PublishJobStatus,
)
from app.schemas.schemas import PlanDefinition, PlanKey

# Static Plan Definitions
PLANS = {
    PlanKey.FREE: PlanDefinition(
        key=PlanKey.FREE,
        name="Free",
        ai_generations_per_month=5,
        renders_per_month=3,
        publishes_per_month=2,
        scheduled_publishes_limit=1,
        watermark_enabled=True,
    ),
    PlanKey.CREATOR: PlanDefinition(
        key=PlanKey.CREATOR,
        name="Creator",
        ai_generations_per_month=50,
        renders_per_month=30,
        publishes_per_month=30,
        scheduled_publishes_limit=20,
        watermark_enabled=False,
    ),
    PlanKey.PRO: PlanDefinition(
        key=PlanKey.PRO,
        name="Pro",
        ai_generations_per_month=200,
        renders_per_month=150,
        publishes_per_month=150,
        scheduled_publishes_limit=100,
        watermark_enabled=False,
    ),
}

def get_current_period_bounds() -> tuple[datetime, datetime]:
    # For now, simplistic monthly periods from the start of the current month
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    # Next month start (handle December rollover)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return start, end

async def get_workspace_plan(db: AsyncSession, workspace_id: uuid.UUID) -> PlanDefinition:
    stmt = select(WorkspaceSubscription).where(
        WorkspaceSubscription.workspace_id == workspace_id,
        WorkspaceSubscription.status == SubscriptionStatus.ACTIVE
    )
    result = await db.execute(stmt)
    sub = result.scalar_one_or_none()
    
    plan_key = PlanKey(sub.plan_key) if sub else PlanKey.FREE
    return PLANS[plan_key]

async def get_or_create_current_usage_counter(db: AsyncSession, workspace_id: uuid.UUID) -> UsageCounter:
    start, end = get_current_period_bounds()
    
    stmt = select(UsageCounter).where(
        UsageCounter.workspace_id == workspace_id,
        UsageCounter.period_start == start,
        UsageCounter.period_end == end
    )
    result = await db.execute(stmt)
    counter = result.scalar_one_or_none()
    
    if not counter:
        counter = UsageCounter(
            workspace_id=workspace_id,
            period_start=start,
            period_end=end,
        )
        db.add(counter)
        await db.commit()
        await db.refresh(counter)
        
    return counter

async def count_active_scheduled_jobs(db: AsyncSession, workspace_id: uuid.UUID) -> int:
    stmt = select(func.count(PublishJob.id)).join(PublishJob.project).where(
        PublishJob.status == PublishJobStatus.SCHEDULED,
        # Accessing project.workspace_id
        # Wait, the models.py defines PublishJob.project -> ReelProject, which has workspace_id
    )
    from app.models.models import ReelProject
    stmt = select(func.count(PublishJob.id)).join(ReelProject, PublishJob.project_id == ReelProject.id).where(
        PublishJob.status == PublishJobStatus.SCHEDULED,
        ReelProject.workspace_id == workspace_id
    )
    result = await db.execute(stmt)
    return result.scalar_one() or 0

async def get_usage_summary(db: AsyncSession, workspace_id: uuid.UUID):
    plan = await get_workspace_plan(db, workspace_id)
    counter = await get_or_create_current_usage_counter(db, workspace_id)
    active_schedules = await count_active_scheduled_jobs(db, workspace_id)
    
    from app.schemas.schemas import UsageSummaryResponse
    return UsageSummaryResponse(
        plan=plan,
        period_start=counter.period_start,
        period_end=counter.period_end,
        ai_generations_used=counter.ai_generations_used,
        ai_generations_limit=plan.ai_generations_per_month,
        renders_used=counter.renders_used,
        renders_limit=plan.renders_per_month,
        publishes_used=counter.publishes_used,
        publishes_limit=plan.publishes_per_month,
        active_scheduled_publishes=active_schedules,
        scheduled_publishes_limit=plan.scheduled_publishes_limit
    )

async def check_usage_limit(db: AsyncSession, workspace_id: uuid.UUID, event_type: UsageEventType, throw_if_exceeded: bool = True) -> bool:
    plan = await get_workspace_plan(db, workspace_id)
    counter = await get_or_create_current_usage_counter(db, workspace_id)
    
    used = 0
    limit = 0
    message = ""
    
    if event_type == UsageEventType.AI_GENERATION:
        used = counter.ai_generations_used
        limit = plan.ai_generations_per_month
        message = "You have reached your monthly AI generation limit."
    elif event_type == UsageEventType.RENDER:
        used = counter.renders_used
        limit = plan.renders_per_month
        message = "You have reached your monthly render limit."
    elif event_type == UsageEventType.PUBLISH:
        used = counter.publishes_used
        limit = plan.publishes_per_month
        message = "You have reached your monthly publish limit."
    elif event_type == UsageEventType.SCHEDULED_PUBLISH:
        used = await count_active_scheduled_jobs(db, workspace_id)
        limit = plan.scheduled_publishes_limit
        message = "You have reached your active scheduled publish limit."
        
    exceeded = used >= limit
    
    if exceeded and throw_if_exceeded:
        raise HTTPException(status_code=402, detail={
            "code": "USAGE_LIMIT_EXCEEDED",
            "message": message,
            "plan_key": plan.key.value,
            "limit": limit,
            "used": used,
            "upgrade_required": True
        })
        
    return not exceeded

async def consume_usage(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    event_type: UsageEventType,
    related_project_id: uuid.UUID | None = None,
    related_version_id: uuid.UUID | None = None,
    related_job_id: str | None = None,
    quantity: int = 1
):
    # Check limit first
    await check_usage_limit(db, workspace_id, event_type, throw_if_exceeded=True)
    
    # Optional idempotency via related_job_id
    if related_job_id:
        stmt = select(UsageEvent).where(
            UsageEvent.workspace_id == workspace_id,
            UsageEvent.event_type == event_type,
            UsageEvent.related_job_id == related_job_id
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            return # Already consumed
            
    # Add usage event
    event = UsageEvent(
        workspace_id=workspace_id,
        user_id=user_id,
        event_type=event_type,
        quantity=quantity,
        related_project_id=related_project_id,
        related_version_id=related_version_id,
        related_job_id=related_job_id
    )
    db.add(event)
    
    # Update counter
    counter = await get_or_create_current_usage_counter(db, workspace_id)
    if event_type == UsageEventType.AI_GENERATION:
        counter.ai_generations_used += quantity
    elif event_type == UsageEventType.RENDER:
        counter.renders_used += quantity
    elif event_type == UsageEventType.PUBLISH:
        counter.publishes_used += quantity
    elif event_type == UsageEventType.SCHEDULED_PUBLISH:
        counter.scheduled_publishes_created += quantity
        
    await db.commit()


async def refund_usage(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    event_type: UsageEventType,
    quantity: int = 1,
    related_job_id: str | None = None,
) -> bool:
    """
    Refund (decrement) a usage counter for rollback scenarios.
    If related_job_id is provided, also removes the matching usage event
    to prevent re-use of the idempotency key on retry.
    Returns True if a refund was applied, False if nothing to refund.
    """
    counter = await get_or_create_current_usage_counter(db, workspace_id)
    refunded = False

    if event_type == UsageEventType.AI_GENERATION and counter.ai_generations_used > 0:
        counter.ai_generations_used = max(0, counter.ai_generations_used - quantity)
        refunded = True
    elif event_type == UsageEventType.RENDER and counter.renders_used > 0:
        counter.renders_used = max(0, counter.renders_used - quantity)
        refunded = True
    elif event_type == UsageEventType.PUBLISH and counter.publishes_used > 0:
        counter.publishes_used = max(0, counter.publishes_used - quantity)
        refunded = True
    elif event_type == UsageEventType.SCHEDULED_PUBLISH and counter.scheduled_publishes_created > 0:
        counter.scheduled_publishes_created = max(0, counter.scheduled_publishes_created - quantity)
        refunded = True

    # Optionally remove the usage event to allow idempotent retry
    if refunded and related_job_id:
        stmt = select(UsageEvent).where(
            UsageEvent.workspace_id == workspace_id,
            UsageEvent.event_type == event_type,
            UsageEvent.related_job_id == related_job_id,
        )
        result = await db.execute(stmt)
        event = result.scalar_one_or_none()
        if event:
            await db.delete(event)

    if refunded:
        await db.commit()

    return refunded
