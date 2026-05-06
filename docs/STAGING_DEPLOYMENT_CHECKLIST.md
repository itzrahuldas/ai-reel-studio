# Staging Deployment Checklist

**Last Updated:** 2026-05-06

## Pre-Deploy

- [ ] GitHub CI is green for the staging deployment branch.
- [ ] `.env.staging` exists on the staging host and is not committed.
- [ ] `APP_ENV=staging`.
- [ ] `DEBUG=false`.
- [ ] `GENERATION_MODE=async`, `RENDER_MODE=async`, `PUBLISH_MODE=async`.
- [ ] `AI_PROVIDER=mock`, `IMAGE_ANALYSIS_PROVIDER=mock`, `TTS_PROVIDER=mock`.
- [ ] `INSTAGRAM_INTEGRATION_MODE=mock`.
- [ ] `STRIPE_MODE=mock`.
- [ ] Staging Postgres is ready.
- [ ] Staging Redis is ready.
- [ ] Storage is ready: S3/R2 preferred, local persistent disk acceptable for mock-only staging.
- [ ] `FRONTEND_URL`, `API_PUBLIC_BASE_URL`, and `NEXT_PUBLIC_API_URL` are configured.
- [ ] SSL/TLS is configured for public frontend and API URLs.
- [ ] `ALLOWED_ORIGINS` is restricted to the staging frontend origin.
- [ ] Smoke test GitHub secrets `SMOKE_TEST_EMAIL` and `SMOKE_TEST_PASSWORD` are configured.

## Deploy

- [ ] Build API image.
- [ ] Build worker image.
- [ ] Build web image with staging `NEXT_PUBLIC_API_URL`.
- [ ] Run Alembic migrations.
- [ ] Start API service.
- [ ] Start web service.
- [ ] Start `worker-generation`.
- [ ] Start `worker-rendering`.
- [ ] Start `worker-publishing`.
- [ ] Start exactly one `celery-beat`.
- [ ] Confirm no Postgres or Redis ports are publicly exposed.

## Verify

- [ ] `GET /health` returns `status=ok`.
- [ ] `GET /api/v1/health/readiness` returns `ready`.
- [ ] `GET /api/v1/health/config` returns safe mode/config summary only.
- [ ] Frontend root loads.
- [ ] Register/login works with the smoke account.
- [ ] Billing plans and usage load.
- [ ] Mock billing path is skipped or works as expected for the environment mode.
- [ ] Create reel works.
- [ ] Render works.
- [ ] Instagram mock publish is skipped or works as expected for the environment mode.
- [ ] Scheduled publish flow creates a scheduled/queued job when mock route is enabled.
- [ ] Manual `Staging Smoke` GitHub workflow passes.

## Post-Deploy

- [ ] Review API logs for startup errors.
- [ ] Review worker logs for import, broker, and task errors.
- [ ] Review Celery Beat logs for scheduler ticks.
- [ ] Verify no secrets are printed in logs.
- [ ] Verify worker queues are consuming expected tasks.
- [ ] Verify generated media URLs resolve from outside the deployment network.
- [ ] Verify local persistent volume or object storage retains uploaded/generated media.
- [ ] Record deployed branch and commit in release notes.
