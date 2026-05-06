# MVP Release Checklist

**Last Updated:** 2026-05-05

## Local Readiness

- [x] `.env.example` contains the current app, database, Redis, auth, storage, Meta, Stripe, AI, runtime mode, upload, and frontend variables.
- [x] Mock mode remains the default for Instagram, Stripe, and AI providers.
- [x] `apps/web/tsconfig.tsbuildinfo` is ignored as generated TypeScript cache.
- [x] Backend lint is configured for the current codebase.
- [x] Frontend lint and typecheck pass locally.

## CI Gates

- [x] GitHub Actions config installs backend dependencies from `apps/api/pyproject.toml`.
- [x] CI provides Postgres and Redis services.
- [x] CI runs backend Ruff, Alembic upgrade/history/heads, pytest, and worker import validation.
- [x] CI runs frontend install, lint, typecheck, and build.
- [x] Manual staging smoke workflow is available through GitHub Actions.
- [ ] Confirm the updated CI workflow passes on GitHub after push.

## Staging Launch Gates

- [ ] Apply Alembic migrations to the staging database.
- [ ] Configure `APP_ENV=staging`.
- [ ] Configure exact `ALLOWED_ORIGINS` and `FRONTEND_URL`.
- [ ] Configure `API_PUBLIC_BASE_URL` and `STORAGE_PUBLIC_BASE_URL` as HTTPS URLs.
- [ ] Verify `/health`, `/api/v1/health/readiness`, and `/api/v1/health/config`.
- [ ] Run `api`, `worker-generation`, `worker-rendering`, `worker-publishing`, and `celery-beat`.
- [ ] Verify Redis queue connectivity and Celery Beat schedule.
- [ ] Verify FFmpeg is installed in the rendering runtime.
- [ ] Configure S3/R2 or another public HTTPS object storage path.
- [ ] Verify public media URLs work from outside the deployment network.
- [ ] Configure Stripe test mode, Checkout, Customer Portal, and webhooks.
- [ ] Configure Meta OAuth callback for the staging/test app.
- [ ] Configure OpenAI keys if testing `openai` provider mode.
- [ ] Run a full test account flow: register, create, render, connect Instagram, publish mock/test, upgrade mock/test billing.
- [ ] Run `python scripts/staging_smoke_test.py` against the deployed API/frontend.
- [ ] Run the manual `Staging Smoke` GitHub Actions workflow with the same staging URLs.

## Production Launch Gates

- [ ] CI is passing on the release branch.
- [ ] Database backup and rollback plan are prepared.
- [ ] Alembic migrations applied successfully.
- [ ] `APP_ENV=production`.
- [ ] `INSTAGRAM_INTEGRATION_MODE=live`.
- [ ] `STRIPE_MODE=live`.
- [ ] Stripe live recurring Price IDs configured for Creator and Pro.
- [ ] Stripe live webhook endpoint configured with signing secret.
- [ ] Meta OAuth callback uses production HTTPS URL.
- [ ] Meta App Review assets are ready.
- [ ] Terms, privacy policy, and data deletion URLs are ready.
- [ ] OpenAI provider keys configured server-side only.
- [ ] Redis workers and Celery Beat running.
- [ ] FFmpeg installed in rendering workers.
- [ ] Public HTTPS media URLs verified for Instagram.
- [ ] S3/R2 lifecycle and access controls configured.
- [ ] CORS restricted to production frontend only.
- [ ] Live Stripe checkout tested with a real test purchase path before opening to users.

## Current Status

- **Production readiness pass:** completed locally.
- **Staging readiness:** ready for CI verification and managed environment configuration.
- **Production readiness:** not cleared until live Stripe, Meta, OpenAI, object storage, legal URLs, and CI run are verified.
