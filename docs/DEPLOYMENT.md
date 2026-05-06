# Deployment Guide - AI Reel Studio

**Version:** 0.1.0
**Last Updated:** 2026-05-05

This guide describes a production-grade deployment shape after Stripe billing
and Real AI Provider Phase 1. It does not require custom card forms, direct
Instagram password access, or real AI video providers.

## Recommended Architecture

Use separate deployable services:

| Service | Purpose | Notes |
| --- | --- | --- |
| `web` | Next.js dashboard | Vercel, Cloudflare Pages, Render, ECS, or Docker Compose |
| `api` | FastAPI API | Runs auth, billing, upload, project, render, publish APIs |
| `worker-generation` | Celery generation queue | Runs AI planning, image analysis, TTS |
| `worker-rendering` | Celery rendering queue | Requires FFmpeg |
| `worker-publishing` | Celery publishing queue | Requires outbound Meta Graph API access |
| `celery-beat` | Scheduled publish scanner | Runs periodic Celery Beat schedule |
| `postgres` | Primary database | Managed Postgres recommended |
| `redis` | Queue/cache | Managed Redis recommended |
| `object storage` | Media assets | S3/R2/Supabase Storage recommended |
| `proxy/CDN` | HTTPS, CORS, media delivery | CloudFront, Cloudflare, Nginx, or platform router |

Local Docker Compose includes Postgres, Redis, MinIO, API, web, queue-specific
workers, and Celery Beat. Production can use the same service split on ECS,
Render, Railway, Fly.io, Kubernetes, or separate process types.

## Environment Checklist

See [`.env.example`](../.env.example) for a complete safe template.

Required groups for staging/production:

- App: `APP_ENV`, `FRONTEND_URL`, `API_PUBLIC_BASE_URL`, `ALLOWED_ORIGINS`
- Database: `DATABASE_URL`
- Redis/Celery: `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- Auth/security: `SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`
- Storage/media: `STORAGE_PROVIDER`, `STORAGE_PUBLIC_BASE_URL`, `S3_*`
- Instagram/Meta: `INSTAGRAM_INTEGRATION_MODE`, `META_APP_ID`, `META_APP_SECRET`, `META_REDIRECT_URI`, `META_GRAPH_API_VERSION`
- Stripe: `STRIPE_MODE`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_CREATOR_PRICE_ID`, `STRIPE_PRO_PRICE_ID`
- AI providers: `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, `IMAGE_ANALYSIS_PROVIDER`, `IMAGE_ANALYSIS_MODEL`, `TTS_PROVIDER`, `TTS_MODEL`, `TTS_VOICE`
- Runtime modes: `GENERATION_MODE`, `RENDER_MODE`, `PUBLISH_MODE`
- Uploads: `MAX_UPLOAD_BYTES`
- Frontend: `NEXT_PUBLIC_API_URL`

Never place live secrets in GitHub Actions workflow YAML, frontend env variables,
Dockerfiles, or committed config files.

## Local Docker Compose

```bash
cp .env.example .env
# Fill local .env values if you want live integrations.
docker compose up --build
```

Main URLs:

- Web: `http://localhost:3000`
- API: `http://localhost:8000`
- API health: `http://localhost:8000/health`
- API docs in non-production: `http://localhost:8000/docs`
- MinIO console: `http://localhost:9001`

Run migrations:

```bash
docker compose exec api alembic upgrade head
```

## Production Startup Commands

API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Generation worker:

```bash
celery -A app.main:celery_app worker --loglevel=info --concurrency=2 --queues=generation,default
```

Rendering worker:

```bash
celery -A app.main:celery_app worker --loglevel=info --concurrency=1 --queues=rendering
```

Publishing worker:

```bash
celery -A app.main:celery_app worker --loglevel=info --concurrency=2 --queues=publishing
```

Celery Beat:

```bash
celery -A app.main:celery_app beat --loglevel=info
```

Use `PYTHONPATH=/app:/api_src` when running the worker image that mounts or
copies both `apps/worker` and `apps/api`.

## Database Migrations

Run migrations before shifting traffic to a new API version:

```bash
cd apps/api
alembic heads
alembic upgrade head
alembic current
```

Production migration rules:

- Back up the database first.
- Run migrations once per environment.
- Do not rewrite old Alembic migrations.
- Keep failed migration logs; do not retry blindly if a partial migration ran.

## FFmpeg Requirement

FFmpeg must be installed anywhere `RENDER_MODE=sync` can run or where the
rendering Celery queue runs. The provided API and worker Dockerfiles install
FFmpeg. Managed hosts must include it in the build image or package layer.

## Storage and Public Media URLs

Production Instagram publishing requires media URLs that Meta can fetch over
public HTTPS. Local filesystem URLs are acceptable only for local development or
temporary tunnel testing.

Recommended production storage:

- S3, Cloudflare R2, Supabase Storage, or another S3-compatible service.
- A public HTTPS CDN or signed URL layer.
- `STORAGE_PUBLIC_BASE_URL` configured to the public asset base.
- Lifecycle rules for generated audio/video assets.

Do not expose raw filesystem paths to the frontend. API responses should include
safe API or CDN URLs only.

## Meta OAuth Setup

1. Create or configure the Meta app.
2. Add the production `META_REDIRECT_URI`.
3. Set `INSTAGRAM_INTEGRATION_MODE=live`.
4. Configure required permissions for Instagram publishing.
5. Prepare Meta App Review walkthrough assets.
6. Test with a Meta test user before production users.

OAuth callbacks must use HTTPS in staging and production.

## Stripe Setup

1. Create recurring Stripe Prices for Creator and Pro.
2. Set `STRIPE_CREATOR_PRICE_ID` and `STRIPE_PRO_PRICE_ID`.
3. Set `STRIPE_MODE=live`.
4. Set `STRIPE_SECRET_KEY` server-side only.
5. Add webhook endpoint:
   `https://<api-domain>/api/v1/billing/webhooks/stripe`
6. Subscribe to at least:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
7. Set `STRIPE_WEBHOOK_SECRET`.
8. Test Checkout and Customer Portal with Stripe test mode before live mode.

Webhook signature verification is required in live mode.

## OpenAI Provider Setup

For Real AI Provider Phase 1:

```bash
AI_PROVIDER=openai
IMAGE_ANALYSIS_PROVIDER=openai
TTS_PROVIDER=openai
AI_API_KEY=<server-side secret>
```

OpenAI keys are server-only. Missing keys return setup errors rather than
crashing startup. Mock providers remain the default for local development and CI.

## Health Checks

API:

```bash
curl -f https://<api-domain>/health
curl -f https://<api-domain>/api/v1/health/readiness
curl -f https://<api-domain>/api/v1/health/config
```

`/health` is a lightweight liveness probe. `/api/v1/health/readiness` verifies
database connectivity, Redis/Celery broker reachability for async modes, local
storage writability or object-storage config, and required environment
configuration for active Stripe, Meta, and AI modes. `/api/v1/health/config`
returns only safe mode and configured/not-configured booleans; it must never be
used to expose secrets.

Worker:

```bash
celery -A app.main:celery_app inspect ping
```

Database:

```bash
alembic current
```

Frontend:

```bash
curl -f https://<web-domain>
```

## Rollback Checklist

1. Stop new deployments and pause queue autoscaling.
2. Roll web/API/worker images back to the previous known-good image.
3. Keep Celery Beat running only if the rolled-back code supports the schedule.
4. Check whether the migration is backward compatible before downgrading.
5. Re-run `/health`, `alembic current`, worker ping, Stripe webhook delivery,
   and a mock Instagram publish smoke test.
6. Review failed Celery tasks before retrying them.

## Common Failure Modes

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Checkout setup error | Missing Stripe price or secret | Verify Stripe env and live/test mode |
| Webhook 400 | Missing or wrong `STRIPE_WEBHOOK_SECRET` | Copy signing secret from Stripe webhook endpoint |
| OpenAI setup warning | `AI_API_KEY` missing | Add key or switch provider to `mock` |
| Publish stuck | Meta cannot fetch media | Verify public HTTPS media URL and content type |
| Render failed | FFmpeg missing | Install FFmpeg in render worker image |
| Scheduled jobs not firing | Celery Beat not running | Start `celery-beat` service |
| Queue backlog | Worker not scaled or Redis unavailable | Check Redis and queue-specific workers |
| CORS blocked frontend | `ALLOWED_ORIGINS` wrong | Set exact production frontend origin |

## Staging Gate

Before staging users:

- CI passes with Postgres and Redis services.
- Alembic migrations apply cleanly.
- `/health`, `/api/v1/health/readiness`, and `/api/v1/health/config` respond successfully.
- Stripe test Checkout and webhook succeed.
- Meta OAuth callback works with a test user.
- OpenAI mode and mock mode both start cleanly.
- Rendering worker can invoke FFmpeg.
- Public media URLs are HTTPS and reachable externally.
- Run the staging smoke script:

```bash
SMOKE_API_BASE_URL=https://<api-domain> \
SMOKE_FRONTEND_BASE_URL=https://<web-domain> \
SMOKE_TEST_EMAIL=<test-account-email> \
SMOKE_TEST_PASSWORD=<test-account-password> \
python scripts/staging_smoke_test.py
```

Optional smoke flags:

- `SMOKE_CREATE_REEL=true` uploads a tiny generated PNG, creates a reel, waits
  for generation, starts a render, and waits for render completion.
- `SMOKE_TEST_STRIPE_MOCK=true` runs the development-only mock checkout route
  only when the deployed API reports `APP_ENV=development` and `STRIPE_MODE=mock`.
- `SMOKE_TEST_INSTAGRAM_MOCK=true` runs the development-only mock Instagram
  schedule flow only when the API reports `APP_ENV=development` and mock
  Instagram mode.
