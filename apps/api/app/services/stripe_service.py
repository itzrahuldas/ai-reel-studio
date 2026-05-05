# ruff: noqa: ANN401

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import (
    StripeWebhookEvent,
    SubscriptionStatus,
    User,
    Workspace,
    WorkspaceSubscription,
)
from app.schemas.schemas import PlanKey
from app.services.usage_service import PLANS, get_current_period_bounds

try:  # Stripe is an install dependency, but mock mode should still import cleanly.
    import stripe
except ImportError:  # pragma: no cover - exercised only when dependency is absent.
    stripe = None  # type: ignore[assignment]

logger = structlog.get_logger(__name__)

PAID_PLAN_KEYS = {PlanKey.CREATOR, PlanKey.PRO}
PAID_SUBSCRIPTION_STATUSES = {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING}
PROVIDER_STRIPE = "stripe"
PROVIDER_MOCK_STRIPE = "mock_stripe"
PROVIDER_MANUAL = "manual"


class BillingSetupError(Exception):
    """Raised when billing is requested but Stripe is not configured."""


class BillingForbiddenError(Exception):
    """Raised when a billing action is blocked by environment safety rules."""


class StripeWebhookVerificationError(Exception):
    """Raised when a live Stripe webhook signature is invalid."""


class StripeWebhookProcessingError(Exception):
    """Raised for retryable webhook processing failures."""


class StripeEventIgnoredError(Exception):
    """Raised for safe, non-retryable webhook events we intentionally ignore."""


@dataclass(frozen=True)
class CheckoutSessionResult:
    checkout_url: str
    session_id: str
    mode: str


@dataclass(frozen=True)
class PortalSessionResult:
    portal_url: str
    mode: str
    message: str | None = None


def parse_plan_key(raw_plan_key: str) -> PlanKey:
    try:
        return PlanKey(raw_plan_key.upper())
    except ValueError as exc:
        raise ValueError("Unsupported billing plan.") from exc


def is_mock_mode() -> bool:
    return settings.STRIPE_MODE == "mock"


def is_mock_allowed() -> bool:
    return settings.STRIPE_MODE == "mock" and settings.APP_ENV == "development"


def ensure_mock_allowed() -> None:
    if not is_mock_allowed():
        raise BillingForbiddenError("Mock Stripe mode is only available in development.")


def configure_stripe_client() -> None:
    if stripe is None:
        raise BillingSetupError("Stripe SDK is not installed.")
    if not settings.STRIPE_SECRET_KEY:
        raise BillingSetupError("Stripe live mode requires STRIPE_SECRET_KEY.")

    stripe.api_key = settings.STRIPE_SECRET_KEY
    if settings.STRIPE_API_VERSION:
        stripe.api_version = settings.STRIPE_API_VERSION


def get_price_id_for_plan(plan_key: PlanKey) -> str | None:
    if plan_key == PlanKey.CREATOR:
        return settings.STRIPE_CREATOR_PRICE_ID
    if plan_key == PlanKey.PRO:
        return settings.STRIPE_PRO_PRICE_ID
    return None


def get_plan_key_for_price_id(price_id: str | None) -> PlanKey | None:
    if not price_id:
        return None

    configured_prices = {
        settings.STRIPE_CREATOR_PRICE_ID: PlanKey.CREATOR,
        settings.STRIPE_PRO_PRICE_ID: PlanKey.PRO,
    }
    return configured_prices.get(price_id)


def is_price_configured(plan_key: PlanKey) -> bool:
    return bool(get_price_id_for_plan(plan_key))


def is_checkout_available(plan_key: PlanKey) -> bool:
    if plan_key == PlanKey.FREE:
        return False
    if is_mock_allowed():
        return True
    if settings.STRIPE_MODE == "live":
        return bool(settings.STRIPE_SECRET_KEY and get_price_id_for_plan(plan_key))
    return False


def build_plan_response(plan_key: PlanKey) -> dict[str, Any]:
    plan = PLANS[plan_key].model_dump()
    plan["plan_key"] = plan_key.value
    plan["stripe_price_configured"] = is_price_configured(plan_key)
    plan["checkout_available"] = is_checkout_available(plan_key)
    return plan


def get_checkout_success_url() -> str:
    return (
        settings.STRIPE_CHECKOUT_SUCCESS_URL
        or f"{settings.FRONTEND_URL}/dashboard/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    )


def get_checkout_cancel_url() -> str:
    return (
        settings.STRIPE_CHECKOUT_CANCEL_URL
        or f"{settings.FRONTEND_URL}/dashboard/billing/cancel"
    )


def get_portal_return_url() -> str:
    return (
        settings.STRIPE_CUSTOMER_PORTAL_RETURN_URL
        or f"{settings.FRONTEND_URL}/dashboard/billing"
    )


def _jsonable(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict_recursive"):
        value = value.to_dict_recursive()
    return json.loads(json.dumps(value, default=str))


def _stripe_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _optional_str(value: Any) -> str | None:
    return str(value) if value else None


def _stripe_metadata(obj: Any) -> dict[str, Any]:
    metadata = _stripe_get(obj, "metadata", {}) or {}
    return dict(metadata)


def _timestamp_to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        return datetime.fromtimestamp(int(value), UTC)
    except (TypeError, ValueError):
        return None


def _extract_price_id_from_subscription(subscription: Any) -> str | None:
    items = _stripe_get(subscription, "items", {}) or {}
    data = _stripe_get(items, "data", []) or []
    if not data:
        return None
    first_item = data[0]
    price = _stripe_get(first_item, "price", {}) or {}
    return _stripe_get(price, "id")


def _extract_period_from_subscription(subscription: Any, key: str) -> datetime | None:
    value = _stripe_get(subscription, key)
    if value is None:
        items = _stripe_get(subscription, "items", {}) or {}
        data = _stripe_get(items, "data", []) or []
        if data:
            value = _stripe_get(data[0], key)
    return _timestamp_to_datetime(value)


def _map_subscription_status(raw_status: str | None) -> SubscriptionStatus:
    try:
        return SubscriptionStatus(raw_status or SubscriptionStatus.PAST_DUE.value)
    except ValueError:
        logger.warning("stripe_subscription_status_unknown", stripe_status=raw_status)
        return SubscriptionStatus.PAST_DUE


def get_effective_plan_key(subscription: WorkspaceSubscription | None) -> PlanKey:
    if not subscription:
        return PlanKey.FREE

    try:
        subscription_plan = PlanKey(subscription.plan_key)
    except ValueError:
        logger.warning(
            "workspace_subscription_plan_unknown",
            workspace_id=str(subscription.workspace_id),
        )
        return PlanKey.FREE

    if subscription_plan == PlanKey.FREE:
        return PlanKey.FREE
    if subscription.status in PAID_SUBSCRIPTION_STATUSES:
        return subscription_plan
    return PlanKey.FREE


async def _get_workspace_subscription(
    db: AsyncSession,
    workspace_id: uuid.UUID,
) -> WorkspaceSubscription | None:
    stmt = select(WorkspaceSubscription).where(WorkspaceSubscription.workspace_id == workspace_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_or_create_workspace_subscription(
    db: AsyncSession,
    workspace_id: uuid.UUID,
) -> WorkspaceSubscription:
    subscription = await _get_workspace_subscription(db, workspace_id)
    if subscription:
        return subscription

    period_start, period_end = get_current_period_bounds()
    subscription = WorkspaceSubscription(
        workspace_id=workspace_id,
        plan_key=PlanKey.FREE.value,
        status=SubscriptionStatus.ACTIVE,
        provider=PROVIDER_MANUAL,
        current_period_start=period_start,
        current_period_end=period_end,
        cancel_at_period_end=False,
    )
    db.add(subscription)
    await db.flush()
    return subscription


async def _find_subscription_for_stripe_object(
    db: AsyncSession,
    stripe_object: Any,
) -> WorkspaceSubscription | None:
    metadata = _stripe_metadata(stripe_object)
    workspace_id_raw = metadata.get("workspace_id")
    if workspace_id_raw:
        try:
            return await _get_or_create_workspace_subscription(db, uuid.UUID(str(workspace_id_raw)))
        except ValueError as exc:
            raise StripeEventIgnoredError(
                "Stripe metadata contains an invalid workspace_id."
            ) from exc

    subscription_id = _stripe_get(stripe_object, "id")
    customer_id = _stripe_get(stripe_object, "customer")
    if subscription_id:
        stmt = select(WorkspaceSubscription).where(
            WorkspaceSubscription.stripe_subscription_id == str(subscription_id)
        )
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()
        if subscription:
            return subscription

    if customer_id:
        stmt = select(WorkspaceSubscription).where(
            WorkspaceSubscription.stripe_customer_id == str(customer_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    return None


async def create_or_get_customer_for_workspace(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user: User,
) -> str:
    if settings.STRIPE_MODE == "mock":
        ensure_mock_allowed()
        subscription = await _get_or_create_workspace_subscription(db, workspace_id)
        if not subscription.stripe_customer_id:
            subscription.stripe_customer_id = f"cus_mock_{workspace_id.hex[:24]}"
        return subscription.stripe_customer_id

    configure_stripe_client()
    subscription = await _get_or_create_workspace_subscription(db, workspace_id)
    if subscription.stripe_customer_id:
        return subscription.stripe_customer_id

    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise BillingSetupError("Workspace was not found while creating Stripe customer.")

    customer = await asyncio.to_thread(
        stripe.Customer.create,
        email=user.email,
        name=workspace.name,
        metadata={"workspace_id": str(workspace_id), "user_id": str(user.id)},
    )
    customer_id = str(_stripe_get(customer, "id"))
    subscription.stripe_customer_id = customer_id
    subscription.provider = PROVIDER_STRIPE
    return customer_id


async def create_checkout_session(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user: User,
    plan_key: PlanKey,
) -> CheckoutSessionResult:
    if plan_key == PlanKey.FREE:
        raise ValueError("FREE plan does not require Checkout.")
    if plan_key not in PAID_PLAN_KEYS:
        raise ValueError("Unsupported billing plan.")

    if settings.STRIPE_MODE == "mock":
        result = await mock_checkout_success(db, workspace_id, user.id, plan_key)
        return CheckoutSessionResult(
            checkout_url=(
                f"{settings.FRONTEND_URL}/dashboard/billing/success"
                f"?mock=1&plan={plan_key.value}&session_id={result['session_id']}"
            ),
            session_id=result["session_id"],
            mode="mock",
        )

    price_id = get_price_id_for_plan(plan_key)
    if not price_id:
        raise BillingSetupError(f"Stripe price ID is not configured for {plan_key.value}.")

    configure_stripe_client()
    subscription = await _get_or_create_workspace_subscription(db, workspace_id)
    if (
        subscription.provider == PROVIDER_STRIPE
        and subscription.stripe_subscription_id
        and subscription.status in PAID_SUBSCRIPTION_STATUSES
    ):
        raise ValueError("Use the billing portal to change an existing Stripe subscription.")

    customer_id = await create_or_get_customer_for_workspace(db, workspace_id, user)
    metadata = {
        "workspace_id": str(workspace_id),
        "user_id": str(user.id),
        "plan_key": plan_key.value,
    }
    session = await asyncio.to_thread(
        stripe.checkout.Session.create,
        mode="subscription",
        customer=customer_id,
        client_reference_id=str(workspace_id),
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=get_checkout_success_url(),
        cancel_url=get_checkout_cancel_url(),
        metadata=metadata,
        subscription_data={"metadata": metadata},
    )

    subscription.provider = PROVIDER_STRIPE
    subscription.stripe_customer_id = customer_id
    subscription.stripe_price_id = price_id
    subscription.stripe_checkout_session_id = str(_stripe_get(session, "id"))
    subscription.metadata_json = {
        **(subscription.metadata_json or {}),
        "checkout_plan_key": plan_key.value,
    }
    await db.commit()

    return CheckoutSessionResult(
        checkout_url=str(_stripe_get(session, "url")),
        session_id=str(_stripe_get(session, "id")),
        mode="live",
    )


async def create_customer_portal_session(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user: User,
) -> PortalSessionResult:
    if settings.STRIPE_MODE == "mock":
        ensure_mock_allowed()
        return PortalSessionResult(
            portal_url=f"{settings.FRONTEND_URL}/dashboard/billing?mock_portal=1",
            mode="mock",
            message="Mock billing portal opened.",
        )

    configure_stripe_client()
    customer_id = await create_or_get_customer_for_workspace(db, workspace_id, user)
    session = await asyncio.to_thread(
        stripe.billing_portal.Session.create,
        customer=customer_id,
        return_url=get_portal_return_url(),
    )
    await db.commit()
    return PortalSessionResult(portal_url=str(_stripe_get(session, "url")), mode="live")


async def handle_webhook_event(db: AsyncSession, event: dict[str, Any]) -> dict[str, Any]:
    event_id = str(event.get("id") or "")
    event_type = str(event.get("type") or "")
    if not event_id or not event_type:
        raise StripeWebhookProcessingError("Stripe webhook event is missing id or type.")

    stmt = select(StripeWebhookEvent).where(StripeWebhookEvent.stripe_event_id == event_id)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if record and record.processing_status in {"processed", "ignored"}:
        return {"status": "duplicate", "event_id": event_id, "event_type": event_type}

    if record:
        record.processing_status = "processing"
        record.error_message = None
    else:
        record = StripeWebhookEvent(
            stripe_event_id=event_id,
            event_type=event_type,
            processing_status="processing",
            payload_json=_jsonable(event),
        )
        db.add(record)
        await db.flush()

    try:
        data_object = event.get("data", {}).get("object", {})
        if event_type == "checkout.session.completed":
            await handle_checkout_session_completed(db, data_object)
            record.processing_status = "processed"
        elif event_type in {"customer.subscription.created", "customer.subscription.updated"}:
            await handle_customer_subscription_created_or_updated(db, data_object)
            record.processing_status = "processed"
        elif event_type == "customer.subscription.deleted":
            await handle_customer_subscription_deleted(db, data_object)
            record.processing_status = "processed"
        elif event_type in {"invoice.payment_succeeded", "invoice.payment_failed"}:
            record.processing_status = "ignored"
        else:
            record.processing_status = "ignored"

        record.processed_at = datetime.now(UTC)
        record.error_message = None
        await db.commit()
        return {
            "status": record.processing_status,
            "event_id": event_id,
            "event_type": event_type,
        }
    except StripeEventIgnoredError as exc:
        record.processing_status = "ignored"
        record.error_message = str(exc)
        record.processed_at = datetime.now(UTC)
        await db.commit()
        logger.warning("stripe_webhook_ignored", event_id=event_id, event_type=event_type)
        return {"status": "ignored", "event_id": event_id, "event_type": event_type}
    except Exception as exc:
        record.processing_status = "failed"
        record.error_message = type(exc).__name__
        await db.commit()
        logger.warning("stripe_webhook_failed", event_id=event_id, event_type=event_type)
        raise StripeWebhookProcessingError("Stripe webhook processing failed.") from exc


async def handle_checkout_session_completed(db: AsyncSession, session: Any) -> None:
    metadata = _stripe_metadata(session)
    workspace_id_raw = metadata.get("workspace_id") or _stripe_get(session, "client_reference_id")
    if not workspace_id_raw:
        raise StripeEventIgnoredError("Checkout session has no workspace metadata.")

    try:
        workspace_id = uuid.UUID(str(workspace_id_raw))
    except ValueError as exc:
        raise StripeEventIgnoredError("Checkout session workspace metadata is invalid.") from exc

    subscription = await _get_or_create_workspace_subscription(db, workspace_id)
    subscription.provider = PROVIDER_STRIPE
    subscription.stripe_customer_id = _optional_str(_stripe_get(session, "customer"))
    subscription.stripe_subscription_id = _optional_str(_stripe_get(session, "subscription"))
    subscription.stripe_checkout_session_id = _optional_str(_stripe_get(session, "id"))

    plan_key_raw = metadata.get("plan_key")
    if plan_key_raw:
        try:
            plan_key = PlanKey(str(plan_key_raw).upper())
        except ValueError as exc:
            raise StripeEventIgnoredError("Checkout session plan metadata is invalid.") from exc
        if plan_key in PAID_PLAN_KEYS:
            subscription.plan_key = plan_key.value
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.stripe_price_id = get_price_id_for_plan(plan_key)

    subscription.metadata_json = {
        **(subscription.metadata_json or {}),
        "checkout_completed_at": datetime.now(UTC).isoformat(),
    }

    stripe_subscription_id = subscription.stripe_subscription_id
    if settings.STRIPE_MODE == "live" and stripe_subscription_id:
        retrieved = await _retrieve_subscription(stripe_subscription_id)
        if retrieved:
            await map_stripe_subscription_to_workspace_subscription(db, retrieved)


async def _retrieve_subscription(stripe_subscription_id: str) -> Any | None:
    try:
        configure_stripe_client()
        return await asyncio.to_thread(
            stripe.Subscription.retrieve,
            stripe_subscription_id,
            expand=["items.data.price"],
        )
    except BillingSetupError:
        raise
    except Exception:
        logger.warning("stripe_subscription_retrieve_failed")
        return None


async def handle_customer_subscription_created_or_updated(
    db: AsyncSession,
    subscription: Any,
) -> None:
    await map_stripe_subscription_to_workspace_subscription(db, subscription)


async def handle_customer_subscription_deleted(db: AsyncSession, subscription: Any) -> None:
    workspace_subscription = await _find_subscription_for_stripe_object(db, subscription)
    if not workspace_subscription:
        raise StripeEventIgnoredError("Stripe subscription does not map to a workspace.")

    workspace_subscription.provider = PROVIDER_STRIPE
    workspace_subscription.plan_key = PlanKey.FREE.value
    workspace_subscription.status = SubscriptionStatus.CANCELED
    workspace_subscription.stripe_subscription_id = _optional_str(_stripe_get(subscription, "id"))
    workspace_subscription.stripe_customer_id = _optional_str(_stripe_get(subscription, "customer"))
    workspace_subscription.stripe_price_id = _extract_price_id_from_subscription(subscription)
    workspace_subscription.cancel_at_period_end = bool(
        _stripe_get(subscription, "cancel_at_period_end", False)
    )
    workspace_subscription.current_period_start = (
        _extract_period_from_subscription(subscription, "current_period_start")
        or workspace_subscription.current_period_start
    )
    workspace_subscription.current_period_end = (
        _extract_period_from_subscription(subscription, "current_period_end")
        or workspace_subscription.current_period_end
    )
    workspace_subscription.metadata_json = {
        **(workspace_subscription.metadata_json or {}),
        "stripe_deleted_at": datetime.now(UTC).isoformat(),
    }


async def map_stripe_subscription_to_workspace_subscription(
    db: AsyncSession,
    stripe_subscription: Any,
) -> WorkspaceSubscription:
    workspace_subscription = await _find_subscription_for_stripe_object(db, stripe_subscription)
    if not workspace_subscription:
        raise StripeEventIgnoredError("Stripe subscription does not map to a workspace.")

    status = _map_subscription_status(str(_stripe_get(stripe_subscription, "status") or "past_due"))
    price_id = _extract_price_id_from_subscription(stripe_subscription)
    plan_key = get_plan_key_for_price_id(price_id)

    if status == SubscriptionStatus.CANCELED:
        effective_plan_key = PlanKey.FREE
    elif status in PAID_SUBSCRIPTION_STATUSES:
        if not plan_key:
            raise StripeEventIgnoredError(
                "Stripe subscription has an unknown price ID; configure the matching plan price."
            )
        effective_plan_key = plan_key
    else:
        if not plan_key:
            raise StripeEventIgnoredError(
                "Stripe subscription has an unknown price ID; configure the matching plan price."
            )
        effective_plan_key = plan_key

    workspace_subscription.provider = PROVIDER_STRIPE
    workspace_subscription.plan_key = effective_plan_key.value
    workspace_subscription.status = status
    workspace_subscription.stripe_subscription_id = _optional_str(
        _stripe_get(stripe_subscription, "id")
    )
    workspace_subscription.stripe_customer_id = _optional_str(
        _stripe_get(stripe_subscription, "customer")
    )
    workspace_subscription.stripe_price_id = price_id
    workspace_subscription.cancel_at_period_end = bool(
        _stripe_get(stripe_subscription, "cancel_at_period_end", False)
    )
    workspace_subscription.current_period_start = (
        _extract_period_from_subscription(stripe_subscription, "current_period_start")
        or workspace_subscription.current_period_start
    )
    workspace_subscription.current_period_end = (
        _extract_period_from_subscription(stripe_subscription, "current_period_end")
        or workspace_subscription.current_period_end
    )
    workspace_subscription.metadata_json = {
        **(workspace_subscription.metadata_json or {}),
        "stripe_subscription_status": str(_stripe_get(stripe_subscription, "status") or ""),
    }
    return workspace_subscription


async def get_billing_status(db: AsyncSession, workspace_id: uuid.UUID) -> dict[str, Any]:
    subscription = await _get_workspace_subscription(db, workspace_id)
    effective_plan_key = get_effective_plan_key(subscription)
    subscription_plan_key = PlanKey.FREE
    if subscription:
        try:
            subscription_plan_key = PlanKey(subscription.plan_key)
        except ValueError:
            subscription_plan_key = PlanKey.FREE

    portal_available = False
    if settings.STRIPE_MODE == "mock":
        portal_available = is_mock_allowed()
    elif subscription and subscription.stripe_customer_id:
        portal_available = True

    return {
        "current_plan": effective_plan_key.value,
        "subscription_plan_key": subscription_plan_key.value,
        "subscription_status": (
            subscription.status.value if subscription else SubscriptionStatus.ACTIVE.value
        ),
        "provider": subscription.provider if subscription else PROVIDER_MANUAL,
        "current_period_start": subscription.current_period_start if subscription else None,
        "current_period_end": subscription.current_period_end if subscription else None,
        "cancel_at_period_end": subscription.cancel_at_period_end if subscription else False,
        "billing_portal_available": portal_available,
        "upgrade_available": effective_plan_key != PlanKey.PRO,
        "stripe_mode": settings.STRIPE_MODE,
    }


async def mock_checkout_success(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    plan_key: PlanKey,
) -> dict[str, Any]:
    ensure_mock_allowed()
    if plan_key not in PAID_PLAN_KEYS:
        raise ValueError("Mock checkout only supports paid plans.")

    subscription = await _get_or_create_workspace_subscription(db, workspace_id)
    period_start, period_end = get_current_period_bounds()
    session_id = f"cs_mock_{uuid.uuid4().hex}"
    subscription.plan_key = plan_key.value
    subscription.status = SubscriptionStatus.ACTIVE
    subscription.provider = PROVIDER_MOCK_STRIPE
    subscription.stripe_customer_id = f"cus_mock_{workspace_id.hex[:24]}"
    subscription.stripe_subscription_id = f"sub_mock_{workspace_id.hex[:24]}"
    subscription.stripe_price_id = (
        get_price_id_for_plan(plan_key) or f"price_mock_{plan_key.value.lower()}"
    )
    subscription.stripe_checkout_session_id = session_id
    subscription.current_period_start = period_start
    subscription.current_period_end = period_end
    subscription.cancel_at_period_end = False
    subscription.metadata_json = {
        **(subscription.metadata_json or {}),
        "mock_checkout_completed_at": datetime.now(UTC).isoformat(),
        "mock_user_id": str(user_id),
    }
    await db.commit()
    return {
        "message": f"Mock checkout completed for {plan_key.value}.",
        "plan_key": plan_key.value,
        "session_id": session_id,
    }


def construct_webhook_event(payload: bytes, stripe_signature: str | None) -> dict[str, Any]:
    if settings.STRIPE_MODE == "live":
        configure_stripe_client()
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise BillingSetupError("Stripe live mode requires STRIPE_WEBHOOK_SECRET.")
        if not stripe_signature:
            raise StripeWebhookVerificationError("Missing Stripe signature.")
        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=stripe_signature,
                secret=settings.STRIPE_WEBHOOK_SECRET,
            )
            return _jsonable(event)
        except Exception as exc:
            raise StripeWebhookVerificationError("Invalid Stripe signature.") from exc

    ensure_mock_allowed()
    try:
        return json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise StripeWebhookVerificationError("Invalid webhook JSON payload.") from exc
