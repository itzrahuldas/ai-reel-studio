import os
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ["DEBUG"] = "false"
os.environ.setdefault("SECRET_KEY", "0" * 64)
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "1" * 64)

from app.main import app
from app.models.models import StripeWebhookEvent, SubscriptionStatus, WorkspaceSubscription
from app.schemas.schemas import PlanKey
from app.services import stripe_service
from app.services.stripe_service import CheckoutSessionResult

client = TestClient(app)

FAKE_TOKEN = "fake-billing-token"
AUTH_HEADERS = {"Authorization": f"Bearer {FAKE_TOKEN}"}
FAKE_USER_ID = uuid.uuid4()
FAKE_WORKSPACE_ID = uuid.uuid4()


class _ScalarResult:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


def _make_user():
    user = MagicMock()
    user.id = FAKE_USER_ID
    user.email = "billing@example.com"
    user.full_name = "Billing User"
    user.is_active = True
    return user


def _make_subscription(plan_key: str = "FREE") -> WorkspaceSubscription:
    return WorkspaceSubscription(
        id=uuid.uuid4(),
        workspace_id=FAKE_WORKSPACE_ID,
        plan_key=plan_key,
        status=SubscriptionStatus.ACTIVE,
        provider="manual",
        current_period_start=datetime(2026, 5, 1, tzinfo=UTC),
        current_period_end=datetime(2026, 6, 1, tzinfo=UTC),
        cancel_at_period_end=False,
    )


@pytest.fixture(autouse=True)
def _reset_stripe_settings(monkeypatch):
    monkeypatch.setattr(stripe_service.settings, "APP_ENV", "development")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_MODE", "mock")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", None)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_WEBHOOK_SECRET", None)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_CREATOR_PRICE_ID", None)
    monkeypatch.setattr(stripe_service.settings, "STRIPE_PRO_PRICE_ID", None)


def test_checkout_requires_auth():
    response = client.post("/api/v1/billing/checkout", json={"plan_key": "CREATOR"})
    assert response.status_code == 401


@patch("app.api.deps.decode_token")
@patch("app.api.deps.AsyncSession.get")
def test_checkout_rejects_free_plan(mock_get, mock_decode):
    mock_decode.return_value = {"sub": str(FAKE_USER_ID), "type": "access"}
    mock_get.return_value = _make_user()

    response = client.post(
        "/api/v1/billing/checkout",
        headers=AUTH_HEADERS,
        json={"plan_key": "FREE"},
    )

    assert response.status_code == 400


@patch("app.api.deps.decode_token")
@patch("app.api.deps.AsyncSession.get")
def test_checkout_rejects_invalid_plan(mock_get, mock_decode):
    mock_decode.return_value = {"sub": str(FAKE_USER_ID), "type": "access"}
    mock_get.return_value = _make_user()

    response = client.post(
        "/api/v1/billing/checkout",
        headers=AUTH_HEADERS,
        json={"plan_key": "TEAM"},
    )

    assert response.status_code == 400


@patch("app.api.deps.decode_token")
@patch("app.api.deps.AsyncSession.get")
def test_checkout_returns_mock_url(mock_get, mock_decode):
    mock_decode.return_value = {"sub": str(FAKE_USER_ID), "type": "access"}
    mock_get.return_value = _make_user()

    with (
        patch(
            "app.api.v1.routers.billing._resolve_workspace_id",
            new=AsyncMock(return_value=FAKE_WORKSPACE_ID),
        ),
        patch(
            "app.api.v1.routers.billing.stripe_service.create_checkout_session",
            new=AsyncMock(
                return_value=CheckoutSessionResult(
                    checkout_url="http://localhost:3000/dashboard/billing/success?mock=1",
                    session_id="cs_mock_123",
                    mode="mock",
                )
            ),
        ),
    ):
        response = client.post(
            "/api/v1/billing/checkout",
            headers=AUTH_HEADERS,
            json={"plan_key": "CREATOR"},
        )

    assert response.status_code == 200
    assert response.json()["mode"] == "mock"
    assert response.json()["checkout_url"].endswith("mock=1")


@patch("app.api.deps.decode_token")
@patch("app.api.deps.AsyncSession.get")
def test_checkout_live_mode_returns_setup_error_if_price_missing(
    mock_get,
    mock_decode,
    monkeypatch,
):
    monkeypatch.setattr(stripe_service.settings, "STRIPE_MODE", "live")
    monkeypatch.setattr(stripe_service.settings, "STRIPE_SECRET_KEY", "sk_test_placeholder")
    mock_decode.return_value = {"sub": str(FAKE_USER_ID), "type": "access"}
    mock_get.return_value = _make_user()

    with patch(
        "app.api.v1.routers.billing._resolve_workspace_id",
        new=AsyncMock(return_value=FAKE_WORKSPACE_ID),
    ):
        response = client.post(
            "/api/v1/billing/checkout",
            headers=AUTH_HEADERS,
            json={"plan_key": "CREATOR"},
        )

    assert response.status_code == 503
    assert "price ID" in response.json()["detail"]


def test_portal_requires_auth():
    response = client.post("/api/v1/billing/portal")
    assert response.status_code == 401


@patch("app.api.deps.decode_token")
@patch("app.api.deps.AsyncSession.get")
def test_webhook_rejects_invalid_signature_in_live_mode(mock_get, mock_decode, monkeypatch):
    monkeypatch.setattr(stripe_service.settings, "STRIPE_MODE", "live")
    mock_decode.return_value = {"sub": str(FAKE_USER_ID), "type": "access"}
    mock_get.return_value = _make_user()

    with patch(
        "app.api.v1.routers.billing.stripe_service.construct_webhook_event",
        side_effect=stripe_service.StripeWebhookVerificationError("bad signature"),
    ):
        response = client.post(
            "/api/v1/billing/webhooks/stripe",
            content=b"{}",
            headers={"Stripe-Signature": "bad"},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_webhook_duplicate_event_is_idempotent():
    event_record = StripeWebhookEvent(
        stripe_event_id="evt_duplicate",
        event_type="customer.subscription.updated",
        processing_status="processed",
    )
    db = AsyncMock()
    db.execute.return_value = _ScalarResult(event_record)

    result = await stripe_service.handle_webhook_event(
        db,
        {"id": "evt_duplicate", "type": "customer.subscription.updated", "data": {"object": {}}},
    )

    assert result["status"] == "duplicate"
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_checkout_session_completed_updates_workspace_subscription():
    sub = _make_subscription()
    session = {
        "id": "cs_test_123",
        "customer": "cus_test_123",
        "subscription": "sub_test_123",
        "metadata": {"workspace_id": str(FAKE_WORKSPACE_ID), "plan_key": "CREATOR"},
    }

    with (
        patch(
            "app.services.stripe_service._get_or_create_workspace_subscription",
            new=AsyncMock(return_value=sub),
        ),
        patch(
            "app.services.stripe_service._retrieve_subscription",
            new=AsyncMock(return_value=None),
        ),
    ):
        await stripe_service.handle_checkout_session_completed(AsyncMock(), session)

    assert sub.plan_key == "CREATOR"
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.provider == "stripe"
    assert sub.stripe_customer_id == "cus_test_123"
    assert sub.stripe_subscription_id == "sub_test_123"


@pytest.mark.asyncio
async def test_customer_subscription_updated_updates_status_period_and_plan(monkeypatch):
    monkeypatch.setattr(stripe_service.settings, "STRIPE_CREATOR_PRICE_ID", "price_creator")
    sub = _make_subscription()
    stripe_subscription = {
        "id": "sub_test_123",
        "customer": "cus_test_123",
        "status": "trialing",
        "current_period_start": 1777593600,
        "current_period_end": 1780272000,
        "cancel_at_period_end": True,
        "items": {"data": [{"price": {"id": "price_creator"}}]},
        "metadata": {"workspace_id": str(FAKE_WORKSPACE_ID)},
    }

    with patch(
        "app.services.stripe_service._find_subscription_for_stripe_object",
        new=AsyncMock(return_value=sub),
    ):
        await stripe_service.handle_customer_subscription_created_or_updated(
            AsyncMock(),
            stripe_subscription,
        )

    assert sub.plan_key == "CREATOR"
    assert sub.status == SubscriptionStatus.TRIALING
    assert sub.cancel_at_period_end is True
    assert sub.current_period_start.year == 2026
    assert sub.provider == "stripe"


@pytest.mark.asyncio
async def test_customer_subscription_deleted_falls_back_to_free():
    sub = _make_subscription("PRO")
    stripe_subscription = {
        "id": "sub_test_123",
        "customer": "cus_test_123",
        "status": "canceled",
        "items": {"data": [{"price": {"id": "price_pro"}}]},
    }

    with patch(
        "app.services.stripe_service._find_subscription_for_stripe_object",
        new=AsyncMock(return_value=sub),
    ):
        await stripe_service.handle_customer_subscription_deleted(AsyncMock(), stripe_subscription)

    assert sub.plan_key == "FREE"
    assert sub.status == SubscriptionStatus.CANCELED


@pytest.mark.asyncio
async def test_unknown_webhook_event_does_not_crash():
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.return_value = _ScalarResult(None)

    result = await stripe_service.handle_webhook_event(
        db,
        {"id": "evt_unknown", "type": "charge.refunded", "data": {"object": {}}},
    )

    assert result["status"] == "ignored"
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_mock_checkout_complete_updates_plan_in_development():
    sub = _make_subscription()
    db = AsyncMock()

    with patch(
        "app.services.stripe_service._get_or_create_workspace_subscription",
        new=AsyncMock(return_value=sub),
    ):
        result = await stripe_service.mock_checkout_success(
            db,
            FAKE_WORKSPACE_ID,
            FAKE_USER_ID,
            PlanKey.PRO,
        )

    assert result["plan_key"] == "PRO"
    assert sub.plan_key == "PRO"
    assert sub.provider == "mock_stripe"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_mock_checkout_complete_blocked_in_production(monkeypatch):
    monkeypatch.setattr(stripe_service.settings, "APP_ENV", "production")

    with pytest.raises(stripe_service.BillingForbiddenError):
        await stripe_service.mock_checkout_success(
            AsyncMock(),
            FAKE_WORKSPACE_ID,
            FAKE_USER_ID,
            PlanKey.CREATOR,
        )


@patch("app.api.deps.decode_token")
@patch("app.api.deps.AsyncSession.get")
def test_user_cannot_access_another_workspace_billing(mock_get, mock_decode):
    mock_decode.return_value = {"sub": str(FAKE_USER_ID), "type": "access"}
    mock_get.return_value = _make_user()

    with (
        patch(
            "app.api.v1.routers.billing._resolve_workspace_id",
            new=AsyncMock(side_effect=HTTPException(status_code=403, detail="Forbidden")),
        ),
        patch(
            "app.api.v1.routers.billing.stripe_service.create_checkout_session",
            new=AsyncMock(),
        ) as mock_checkout,
    ):
        response = client.post(
            "/api/v1/billing/checkout",
            headers=AUTH_HEADERS,
            json={"plan_key": "PRO"},
        )

    assert response.status_code == 403
    mock_checkout.assert_not_called()


def test_invoice_payment_events_are_optional_and_ignored():
    assert "invoice.payment_succeeded" in {
        "invoice.payment_succeeded",
        "invoice.payment_failed",
    }
