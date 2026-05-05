# Feature Report: Stripe Subscription Billing

**Date:** 2026-05-05
**Branch:** `feature/stripe-subscription-billing`
**Status:** Implemented

## 1. Summary

AI Reel Studio now connects the internal `FREE`, `CREATOR`, and `PRO` plan system to Stripe Checkout subscriptions, Stripe webhooks, and the Stripe Customer Portal.

Workspaces still start on `FREE`. Paid limits apply only when the workspace subscription status is `active` or `trialing`. Canceled, unpaid, past-due, incomplete, and unknown subscription states resolve to `FREE` for usage enforcement.

## 2. User Workflow

1. User opens `/dashboard/billing`.
2. The page loads plans and current usage.
3. User clicks `Upgrade` for `CREATOR` or `PRO`.
4. Backend creates a Stripe Checkout Session in subscription mode.
5. User completes hosted Checkout on Stripe.
6. Stripe sends webhooks to `/api/v1/billing/webhooks/stripe`.
7. Backend updates `workspace_subscriptions`.
8. Usage limits immediately reflect the effective plan.
9. User clicks `Manage Billing` to open the Stripe Customer Portal.

## 3. Stripe Checkout Behavior

- `FREE` never creates Checkout.
- `CREATOR` maps to `STRIPE_CREATOR_PRICE_ID`.
- `PRO` maps to `STRIPE_PRO_PRICE_ID`.
- Checkout Session metadata includes `workspace_id`, `user_id`, and `plan_key`.
- Live mode returns a clear setup error if the secret key or target price ID is missing.
- Existing active Stripe subscriptions are managed through the portal to avoid accidental duplicate subscriptions.

## 4. Stripe Customer Portal Behavior

`POST /api/v1/billing/portal` creates a hosted Stripe Customer Portal Session. If the workspace has no Stripe customer yet, the backend creates one safely in live mode and stores only the Stripe customer ID.

## 5. Webhook Behavior

Handled events:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_succeeded` (stored and ignored)
- `invoice.payment_failed` (stored and ignored)

Unknown events are stored and marked ignored. Duplicate Stripe event IDs are idempotent and return success without reprocessing.

## 6. Mock Mode Behavior

When `APP_ENV=development` and `STRIPE_MODE=mock`:

- Checkout does not call Stripe.
- Mock checkout immediately updates the workspace subscription.
- The billing page shows a clearly labeled `Mock upgrade` button.
- `POST /api/v1/billing/dev/mock-checkout-complete` can simulate checkout completion.
- Mock mode is blocked outside development.

## 7. Database Changes

Migration `0008_add_stripe_subscription_fields.py` adds Stripe provider fields to `workspace_subscriptions` and creates `stripe_webhook_events` for webhook audit and idempotency.

New subscription fields:

- `provider`
- `stripe_customer_id`
- `stripe_subscription_id`
- `stripe_price_id`
- `stripe_checkout_session_id`

New webhook table:

- `stripe_event_id`
- `event_type`
- `processing_status`
- `processed_at`
- `error_message`
- `payload_json`

## 8. API Endpoints

- `GET /api/v1/billing/plans`
- `GET /api/v1/billing/usage`
- `POST /api/v1/billing/checkout`
- `POST /api/v1/billing/portal`
- `POST /api/v1/billing/webhooks/stripe`
- `POST /api/v1/billing/dev/mock-checkout-complete`

Existing development routes remain:

- `POST /api/v1/billing/dev/set-plan`
- `POST /api/v1/billing/dev/grant-usage`

## 9. Security Notes

- The app never handles card data.
- Stripe secret keys and webhook secrets are server-only.
- Live webhooks require Stripe signature verification.
- The webhook route is unauthenticated by design but signature-verified in live mode.
- Mock billing routes are development-only.
- Billing operations resolve the current user's workspace server-side.

## 10. Environment Variables

Required for billing configuration:

```env
STRIPE_MODE=mock
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_CREATOR_PRICE_ID=
STRIPE_PRO_PRICE_ID=
STRIPE_CUSTOMER_PORTAL_RETURN_URL=
STRIPE_CHECKOUT_SUCCESS_URL=
STRIPE_CHECKOUT_CANCEL_URL=
STRIPE_API_VERSION=
```

## 11. Commands Run

- `python -m compileall app`
- `pytest tests/unit/test_stripe_billing.py --no-cov -q`
- `pytest tests/unit/test_stripe_billing.py tests/unit/test_usage_service.py tests/unit/test_usage_enforcement.py --no-cov -q`
- `ruff check app/services/stripe_service.py app/api/v1/routers/billing.py app/services/usage_service.py tests/unit/test_stripe_billing.py`
- `ruff check alembic/versions/0008_add_stripe_subscription_fields.py`
- `ruff check .`
- `npm run typecheck`
- `npm run lint`
- `alembic heads`
- `alembic history --verbose`
- `python -c "import app.services.stripe_service; import app.workers.celery_client; print('imports-ok')"`
- `docker compose config`

## 12. Test Results

- `tests/unit/test_stripe_billing.py`: 16 passed
- Targeted billing/usage suite: 44 passed
- Touched backend Stripe files passed Ruff.
- Frontend typecheck passed.
- Frontend lint passed with one existing warning in `src/app/dashboard/reels/[id]/page.tsx` about raw `<img>` usage.
- Alembic head validation passed: `0008 (head)`.
- Alembic history validation passed.
- Worker/import validation passed with local placeholder test env variables.
- `docker compose config` could not run because Docker is not installed in this shell.
- Full backend Ruff currently fails on pre-existing lint debt outside this Stripe patch, especially legacy Alembic migrations and older services/tests.
- Full backend pytest currently fails on legacy mocked response-shape expectations and local database connection refusal; the focused billing/usage suite passes.

## 13. Known Gaps

- No Stripe tax, coupon, trial, invoice, or metered usage billing UI yet.
- Plan changes for existing active Stripe subscriptions are delegated to Customer Portal.
- Usage counters align to subscription periods for active/trialing subscriptions; inactive paid statuses fall back to the calendar period and effective `FREE` limits.

## 14. Risks

- Stripe price IDs must match the internal plan mapping exactly.
- Webhook delivery must be configured with the production API URL.
- Customer Portal plan-change behavior depends on Stripe dashboard portal configuration.

## 15. Next Recommended Feature

Add subscription-aware invoice history and payment-status notifications using Stripe Customer Portal links and non-sensitive invoice metadata.
