# Staging Deployment Plan

**Last Updated:** 2026-05-06

## Deployment Goal

Deploy AI Reel Studio to a staging environment that mirrors production topology
while keeping integrations safe:

- `APP_ENV=staging`
- Stripe in `mock`
- Instagram in `mock`
- AI providers in `mock`
- async workers and Celery Beat enabled

This plan does not deploy production, does not use live credentials, and does
not require cloud credentials inside the repository.

## Recommended Staging Architecture

| Service | Purpose | Notes |
| --- | --- | --- |
| `web` | Next.js dashboard | Public HTTPS frontend |
| `api` | FastAPI API | Public HTTPS API |
| `worker-generation` | AI planning/TTS queue | Uses `generation,default` queues |
| `worker-rendering` | FFmpeg render queue | Requires FFmpeg in image/runtime |
| `worker-publishing` | Instagram publish queue | Safe in mock mode for staging |
| `celery-beat` | Scheduled publish scanner | Runs periodic scheduler task |
| `postgres` | Primary database | Managed Postgres preferred; Compose fallback included |
| `redis` | Broker/result backend | Managed Redis preferred; Compose fallback included |
| `storage` | Media assets | S3/R2 preferred; local persistent volume acceptable only for non-live publish testing |

## Network And Public URLs

Configure these as HTTPS URLs for staging:

- `FRONTEND_URL=https://app-staging.example.com`
- `API_PUBLIC_BASE_URL=https://api-staging.example.com`
- `NEXT_PUBLIC_API_URL=https://api-staging.example.com`
- `STORAGE_PUBLIC_BASE_URL=https://media-staging.example.com`

For local Compose staging without public DNS, use localhost URLs for initial
deployment checks, then switch to HTTPS before external smoke or Meta testing.

## Required Staging Environment Variables

Start from [`.env.staging.example`](../.env.staging.example). Required groups:

- App: `APP_ENV`, `DEBUG`, `FRONTEND_URL`, `API_PUBLIC_BASE_URL`, `NEXT_PUBLIC_API_URL`, `ALLOWED_ORIGINS`
- Database: `DATABASE_URL`
- Redis/Celery: `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- Security: `SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`
- Storage: `STORAGE_PROVIDER`, `STORAGE_PUBLIC_BASE_URL`, `LOCAL_STORAGE_PATH` or `S3_*`
- Runtime: `GENERATION_MODE`, `RENDER_MODE`, `PUBLISH_MODE`
- Mock integrations: `INSTAGRAM_INTEGRATION_MODE=mock`, `STRIPE_MODE=mock`, `AI_PROVIDER=mock`, `IMAGE_ANALYSIS_PROVIDER=mock`, `TTS_PROVIDER=mock`

## Required Secrets

These must be set in the staging host or secret manager, never in Git:

- `SECRET_KEY`
- `TOKEN_ENCRYPTION_KEY`
- `DATABASE_URL` or `POSTGRES_PASSWORD`
- managed Redis password/URL if used
- object storage credentials if `STORAGE_PROVIDER=s3`
- optional staging Stripe test keys only when testing Stripe-hosted Checkout
- optional Meta test app credentials only when testing OAuth callback
- optional OpenAI key only when explicitly testing `openai` provider mode

## Migration Command

Docker Compose staging:

```bash
bash scripts/run_staging_migrations.sh .env.staging
```

Manual API container:

```bash
cd apps/api
APP_ENV=staging alembic heads
APP_ENV=staging alembic upgrade head
APP_ENV=staging alembic current
```

Never print or paste `DATABASE_URL` in logs or screenshots.

## Worker Commands

Generation:

```bash
celery -A app.main:celery_app worker --loglevel=info --concurrency=2 --queues=generation,default
```

Rendering:

```bash
celery -A app.main:celery_app worker --loglevel=info --concurrency=1 --queues=rendering
```

Publishing:

```bash
celery -A app.main:celery_app worker --loglevel=info --concurrency=2 --queues=publishing
```

## Celery Beat Command

```bash
celery -A app.main:celery_app beat --loglevel=info
```

Run exactly one Celery Beat process per staging environment.

## Health Check URLs

- `GET https://api-staging.example.com/health`
- `GET https://api-staging.example.com/api/v1/health/readiness`
- `GET https://api-staging.example.com/api/v1/health/config`

Readiness should be `ready` before smoke tests. `degraded` requires review.
`not_ready` blocks staging promotion.

## Smoke Test Command

```bash
SMOKE_API_BASE_URL=https://api-staging.example.com \
SMOKE_FRONTEND_BASE_URL=https://app-staging.example.com \
SMOKE_TEST_EMAIL=<staging-smoke-email> \
SMOKE_TEST_PASSWORD='<staging-smoke-password>' \
SMOKE_CREATE_REEL=true \
SMOKE_TEST_STRIPE_MOCK=true \
SMOKE_TEST_INSTAGRAM_MOCK=true \
python scripts/staging_smoke_test.py
```

For `APP_ENV=staging`, development-only mock Stripe and Instagram routes are
expected to be skipped unless a staging environment is intentionally configured
to expose those development mock routes.

## Rollback Steps

1. Stop new deploys and pause queue scaling.
2. Roll web/API/worker images to the previous known-good tag or commit.
3. Keep Celery Beat running only if the rolled-back code supports the schedule.
4. Check whether applied migrations are backward compatible before downgrading.
5. Re-run health checks and smoke tests.
6. Review failed Celery tasks before retrying.

## Common Staging Failures And Fixes

| Failure | Likely Cause | Fix |
| --- | --- | --- |
| `/health` unavailable | API container down or routing misconfigured | Check API logs, proxy, and container health |
| readiness database failed | DB URL, firewall, SSL, or migration issue | Validate managed DB access from API network |
| readiness Redis failed | Redis URL/firewall/auth mismatch | Validate Redis URL and worker broker settings |
| media URLs inaccessible | Local storage without public HTTPS | Configure S3/R2 or HTTPS static media proxy |
| render jobs stuck | Rendering worker down or FFmpeg unavailable | Check `worker-rendering` logs and image packages |
| scheduled jobs not firing | Celery Beat missing | Start one `celery-beat` service |
| smoke auth fails | Existing smoke user password mismatch | Reset smoke account or use a fresh email |
| smoke create returns 402 | Smoke workspace quota exhausted | Use new smoke user or reset test billing state |
