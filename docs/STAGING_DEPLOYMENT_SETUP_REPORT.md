# Staging Deployment Setup Report

**Branch:** `chore/staging-deployment-setup`
**Date:** 2026-05-06

## Summary

Prepared staging deployment artifacts for AI Reel Studio without using production
credentials or deploying to a cloud provider from this workspace.

The setup is Docker Compose based by default and includes documentation for
managed-platform alternatives.

## Files Added

- `.env.staging.example`
- `docker-compose.staging.yml`
- `scripts/deploy_staging.sh`
- `scripts/run_staging_migrations.sh`
- `docs/STAGING_DEPLOYMENT_PLAN.md`
- `docs/STAGING_DEPLOYMENT_CHECKLIST.md`

## Files Updated

- `.gitignore`
- `.dockerignore`
- `README.md`
- `docs/DEPLOYMENT.md`
- `docs/STAGING_SMOKE_TESTS.md`
- `docs/CHANGELOG.md`

## Staging Defaults

- `APP_ENV=staging`
- `DEBUG=false`
- `GENERATION_MODE=async`
- `RENDER_MODE=async`
- `PUBLISH_MODE=async`
- `AI_PROVIDER=mock`
- `IMAGE_ANALYSIS_PROVIDER=mock`
- `TTS_PROVIDER=mock`
- `INSTAGRAM_INTEGRATION_MODE=mock`
- `STRIPE_MODE=mock`

## Deployment Command

```bash
cp .env.staging.example .env.staging
# Fill .env.staging on the staging host.
bash scripts/deploy_staging.sh .env.staging
```

## Migration Command

```bash
bash scripts/run_staging_migrations.sh .env.staging
```

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

## Commands Run

```bash
git status --short --branch
git branch --show-current
git remote -v
git log --oneline -8
git diff --stat
git switch chore/staging-smoke-tests
git switch -c chore/staging-deployment-setup
git cherry-pick 93d9f8cf09df06bd646060285ccdabf7fb40e267
bash -n scripts/deploy_staging.sh scripts/run_staging_migrations.sh
python -m compileall scripts
python -m ruff check alembic
alembic heads
alembic history --verbose
npm ci
npm run lint
npm run typecheck
npm run build
docker compose --env-file .env.staging.example -f docker-compose.staging.yml config
alembic upgrade head
pytest -q
git diff --check
```

## Test Results

- Shell syntax: `bash -n` passed for staging scripts.
- ShellCheck: unavailable in this local shell.
- Python script compile: passed.
- Backend Ruff on Alembic files: passed.
- Alembic heads/history: passed with single head `0009`.
- Frontend `npm ci`: passed.
- Frontend lint: passed after rerun in CI order.
- Frontend typecheck: passed after rerun in CI order.
- Frontend build: passed.
- Full backend pytest: `80 passed`.
- `docker compose config`: not run because Docker CLI is unavailable locally.
- `alembic upgrade head`: not run locally because Postgres on `localhost:5432`
  refused the connection.

## Known Gaps

- No cloud provider credentials or provider CLI authentication were available or
  assumed, so no actual staging deploy was executed from this workspace.
- Docker CLI is unavailable in this shell, so Compose config/build/deploy must
  be validated on the staging host or CI runner with Docker.
- Local Postgres is unavailable in this shell, so migrations must be applied on
  the staging host or CI runner with the staging database reachable.
- Mock Stripe and mock Instagram routes remain development-only in the API; in
  normal `APP_ENV=staging`, those optional smoke steps are expected to skip.

## Staging Readiness

Ready for a staging operator to fill `.env.staging`, run migrations, start the
Compose stack or equivalent managed services, and execute smoke tests.
