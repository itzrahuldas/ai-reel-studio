# Feature Report: Staging Smoke Tests And Health Checks

**Branch:** `chore/staging-smoke-tests`
**Date:** 2026-05-06

## Summary

Implemented deployment verification for staging through API health endpoints, a
standalone smoke test runner, and a manual GitHub Actions workflow. The feature
adds no product behavior; it only verifies existing liveness, readiness,
authentication, billing, optional reel generation/rendering, and optional mock
integration paths.

## Health Endpoints Added

- `GET /health`: lightweight API liveness with service, environment, and version.
- `GET /api/v1/health/readiness`: checks database, Redis, Celery broker, storage,
  and required configuration for current modes.
- `GET /api/v1/health/config`: safe runtime/provider summary with configured
  booleans and no secret values.

## Smoke Test Script Behavior

Created `scripts/staging_smoke_test.py`. It accepts environment variables for
API/frontend URLs, smoke credentials, timeout, and optional mock checks.

Default smoke mode checks API health, readiness, safe config, frontend reachability
when configured, registration/login, `/auth/me`, billing plans, and billing usage.

Optional flags can add:

- Tiny PNG upload, reel creation, generation polling, render start, and render polling.
- Development-only mock Stripe checkout verification.
- Development-only mock Instagram connect and scheduled publish verification.

The script prints a PASS/FAIL/SKIPPED summary and never prints tokens or secrets.

## GitHub Workflow Behavior

Added `.github/workflows/staging-smoke.yml` as a manual `workflow_dispatch`
workflow. It accepts staging API/frontend URLs and optional boolean flags, reads
smoke credentials from GitHub secrets, and runs the Python smoke script.

It does not run on every push.

## Commands Run

```bash
git status --short --branch
git branch --show-current
git log --oneline -8
git switch -c chore/staging-smoke-tests
python -m ruff check app tests/test_health.py
python -m pytest tests/test_health.py --no-cov -q
python -m pytest tests/test_auth.py tests/test_health.py --no-cov -q
python -m compileall scripts
cd apps/web && npm run lint
cd apps/web && npm run typecheck
cd apps/web && npm run build
docker compose config
git diff --check
```

## Test Results

- Targeted health tests: `3 passed`.
- Auth plus health regression tests: `8 passed`.
- Script compile check: passed.
- Backend Ruff on app plus targeted health tests: passed.
- Frontend lint: passed.
- Frontend typecheck: passed.
- Frontend production build: passed.
- Git diff whitespace check: passed.
- Docker Compose config: not run because Docker CLI is unavailable in the local shell.

## Known Gaps

- The staging smoke script does not create live Stripe Checkout sessions or live
  Meta publish jobs. Live integration verification remains a controlled staging
  or production preflight activity.
- Optional reel/render smoke can consume usage quota for the smoke workspace.
- Readiness marks degraded, rather than failed, for supported non-critical
  warnings so operators can inspect the environment before promotion.
- Docker CLI remains unavailable locally; CI or a Docker-enabled environment
  should continue to validate Compose config.

## Next Recommended Step

Deploy this branch to staging, configure `SMOKE_TEST_EMAIL` and
`SMOKE_TEST_PASSWORD` as GitHub secrets, and run the manual `Staging Smoke`
workflow first in basic mode, then with `SMOKE_CREATE_REEL=true` once workers and
FFmpeg are confirmed running.
