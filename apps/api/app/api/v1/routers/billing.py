"""
Billing & Usage API router.

Endpoints:
  GET  /api/v1/billing/plans          — static plan definitions (public)
  GET  /api/v1/billing/usage          — current workspace usage summary (auth required)

  Development-only (APP_ENV=development):
  POST /api/v1/billing/dev/set-plan   — override workspace plan
  POST /api/v1/billing/dev/grant-usage — grant artificial usage (for testing limits)
"""

from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.models.models import (
    SubscriptionStatus,
    UsageEventType,
    WorkspaceMember,
    WorkspaceSubscription,
)
from app.schemas.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    GrantDevUsageRequest,
    MockCheckoutCompleteRequest,
    PlanDefinition,
    PlanKey,
    PortalResponse,
    SetDevPlanRequest,
    UsageSummaryResponse,
)
from app.services import stripe_service
from app.services.stripe_service import BillingForbiddenError, BillingSetupError
from app.services.usage_service import (
    PLANS,
    get_usage_summary,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


async def _resolve_workspace_id(db: DbSession, current_user: CurrentUser) -> UUID:
    from sqlalchemy import select

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
    return workspace_id


def _parse_paid_plan_or_400(raw_plan_key: str) -> PlanKey:
    try:
        plan_key = stripe_service.parse_plan_key(raw_plan_key)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unsupported billing plan.") from None

    if plan_key == PlanKey.FREE:
        raise HTTPException(status_code=400, detail="FREE plan does not require Checkout.")
    return plan_key


# ── Plan Definitions (public) ─────────────────────────────────────────────────

@router.get("/plans", response_model=list[PlanDefinition])
async def list_plans() -> list[dict[str, object]]:
    """
    Return all available billing plan definitions.
    This endpoint is public — no auth required.
    Useful for pricing pages and upgrade modals.
    """
    return [stripe_service.build_plan_response(plan_key) for plan_key in PLANS]


# ── Usage Summary (auth required) ─────────────────────────────────────────────

@router.get("/usage", response_model=UsageSummaryResponse)
async def get_usage(
    current_user: CurrentUser,
    db: DbSession,
) -> UsageSummaryResponse:
    """
    Return current usage summary for the authenticated user's workspace.

    Response includes:
    - Current plan definition with all limits
    - Current period start/end
    - Usage counts for AI generations, renders, publishes, and scheduled publishes
    - Watermark setting for the plan

    Use this to drive usage bars and upgrade CTAs in the frontend.
    """
    workspace_id = await _resolve_workspace_id(db, current_user)

    return await get_usage_summary(db, workspace_id)


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    data: CheckoutRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> CheckoutResponse:
    """
    Create a Stripe Checkout Session for a paid workspace subscription.
    """
    plan_key = _parse_paid_plan_or_400(data.plan_key)
    workspace_id = await _resolve_workspace_id(db, current_user)
    try:
        session = await stripe_service.create_checkout_session(
            db=db,
            workspace_id=workspace_id,
            user=current_user,
            plan_key=plan_key,
        )
    except BillingForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except BillingSetupError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return CheckoutResponse(
        checkout_url=session.checkout_url,
        session_id=session.session_id,
        mode=session.mode,
    )


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    current_user: CurrentUser,
    db: DbSession,
) -> PortalResponse:
    """
    Create a Stripe Customer Portal session for the current workspace.
    """
    workspace_id = await _resolve_workspace_id(db, current_user)
    try:
        portal = await stripe_service.create_customer_portal_session(
            db=db,
            workspace_id=workspace_id,
            user=current_user,
        )
    except BillingForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except BillingSetupError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return PortalResponse(
        portal_url=portal.portal_url,
        mode=portal.mode,
        message=portal.message,
    )


@router.post("/webhooks/stripe", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    db: DbSession,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict[str, str]:
    """
    Stripe webhook endpoint.

    This route is intentionally unauthenticated. Live mode verifies the
    Stripe-Signature header before any event is processed.
    """
    payload = await request.body()
    try:
        event = stripe_service.construct_webhook_event(payload, stripe_signature)
    except stripe_service.StripeWebhookVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook.",
        ) from exc
    except BillingForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except BillingSetupError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    try:
        return await stripe_service.handle_webhook_event(db, event)
    except stripe_service.StripeWebhookProcessingError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed.",
        ) from None


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
) -> dict[str, object]:
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
        subscription.provider = "manual"
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
            provider="manual",
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
    "/dev/mock-checkout-complete",
    status_code=200,
    dependencies=[DevEnv],
)
async def dev_mock_checkout_complete(
    data: MockCheckoutCompleteRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> dict[str, object]:
    """
    **DEV ONLY** - Complete a mock Stripe checkout for local testing.
    """
    if settings.STRIPE_MODE != "mock":
        raise HTTPException(
            status_code=403,
            detail="Mock checkout completion requires STRIPE_MODE=mock.",
        )

    plan_key = _parse_paid_plan_or_400(data.plan_key)
    workspace_id = await _resolve_workspace_id(db, current_user)
    try:
        result = await stripe_service.mock_checkout_success(
            db=db,
            workspace_id=workspace_id,
            user_id=current_user.id,
            plan_key=plan_key,
        )
    except BillingForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"workspace_id": str(workspace_id), **result}


@router.post(
    "/dev/grant-usage",
    status_code=200,
    dependencies=[DevEnv],
)
async def dev_grant_usage(
    data: GrantDevUsageRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> dict[str, object]:
    """
    **DEV ONLY** — Artificially increment usage counters for testing limit enforcement.

    Example: Grant 10 AI_GENERATION events to test the 402 limit response.
    This bypasses limit checks and directly increments counters + logs events.

    event_type: AI_GENERATION | RENDER | PUBLISH | SCHEDULED_PUBLISH
    """
    from sqlalchemy import select

    from app.models.models import UsageEvent
    from app.services.usage_service import get_or_create_current_usage_counter

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
        ) from None

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
