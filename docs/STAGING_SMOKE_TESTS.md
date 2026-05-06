# Staging Smoke Tests

**Last Updated:** 2026-05-06

## Purpose

The staging smoke test verifies that a deployed AI Reel Studio environment is
alive, correctly configured, and able to execute the critical authenticated
paths without using live Stripe, Meta, or OpenAI credentials by default.

It is intended to run after every staging deploy and before any production
promotion.

## Required Environment Variables

Set these in your shell or GitHub Actions environment:

```bash
SMOKE_API_BASE_URL=https://api-staging.example.com
SMOKE_FRONTEND_BASE_URL=https://app-staging.example.com
SMOKE_TEST_EMAIL=smoke@example.com
SMOKE_TEST_PASSWORD=<staging-smoke-password>
SMOKE_TIMEOUT_SECONDS=180
SMOKE_CREATE_REEL=false
SMOKE_TEST_STRIPE_MOCK=false
SMOKE_TEST_INSTAGRAM_MOCK=false
```

`SMOKE_API_BASE_URL`, `SMOKE_TEST_EMAIL`, and `SMOKE_TEST_PASSWORD` are
required. `SMOKE_FRONTEND_BASE_URL` is optional; frontend checks are marked
skipped when it is not set.

## Run Locally Against Staging

From the repository root:

```bash
SMOKE_API_BASE_URL=https://api-staging.example.com \
SMOKE_FRONTEND_BASE_URL=https://app-staging.example.com \
SMOKE_TEST_EMAIL=smoke@example.com \
SMOKE_TEST_PASSWORD='<staging-smoke-password>' \
python scripts/staging_smoke_test.py
```

To include reel generation and rendering:

```bash
SMOKE_CREATE_REEL=true python scripts/staging_smoke_test.py
```

Full staging validation command:

```bash
SMOKE_API_BASE_URL=https://api-staging.example.com \
SMOKE_FRONTEND_BASE_URL=https://app-staging.example.com \
SMOKE_TEST_EMAIL=smoke@example.com \
SMOKE_TEST_PASSWORD='<staging-smoke-password>' \
SMOKE_CREATE_REEL=true \
SMOKE_TEST_STRIPE_MOCK=true \
SMOKE_TEST_INSTAGRAM_MOCK=true \
python scripts/staging_smoke_test.py
```

The script uses Python standard library HTTP clients and does not require local
application dependencies.

## Run Through GitHub Actions

Use the manual **Staging Smoke** workflow:

1. Open GitHub Actions.
2. Select `Staging Smoke`.
3. Click **Run workflow**.
4. Enter the staging API URL and optional frontend URL.
5. Enable optional mock/reel flags only for environments that support them.

Configure these repository secrets before running the workflow:

- `SMOKE_TEST_EMAIL`
- `SMOKE_TEST_PASSWORD`

Do not store real customer credentials or live integration secrets in workflow
inputs.

## Smoke Steps

The script checks:

- `GET /health` API liveness.
- `GET /api/v1/health/readiness` database, Redis/Celery, storage, and config readiness.
- `GET /api/v1/health/config` safe provider/runtime mode summary.
- Optional frontend routes: `/`, `/login`, and `/dashboard/billing`.
- Test user registration, falling back to login if the user already exists.
- `GET /api/v1/auth/me`.
- `GET /api/v1/billing/plans` and authenticated `GET /api/v1/billing/usage`.
- Optional development-only mock Stripe checkout.
- Optional tiny PNG upload, reel creation, generation polling, render start, and render polling.
- Optional development-only mock Instagram connect plus scheduled publish.

Optional disabled checks are reported as `SKIPPED`, not failures.

## Mock-Mode Requirements

Basic smoke mode does not require Stripe, Meta, or OpenAI live credentials.

Mock Stripe and mock Instagram routes are intentionally development-only:

- Mock Stripe checkout requires `APP_ENV=development` and `STRIPE_MODE=mock`.
- Mock Instagram connect requires `APP_ENV=development` and `INSTAGRAM_INTEGRATION_MODE=mock`.

For `APP_ENV=staging`, those optional flags are normally skipped unless the
environment intentionally exposes development mock routes.

## Interpreting PASS/FAIL

The script prints one line per step:

- `PASS`: the step completed successfully.
- `SKIPPED`: an optional step was disabled or unavailable for the current mode.
- `FAIL`: a required step failed or an enabled optional step failed.

The process exits:

- `0` when there are no failed steps.
- `1` when any smoke step fails.
- `2` when required smoke configuration is missing.

Readiness status `degraded` is allowed so operators can inspect non-critical
warnings without blocking every staging deploy. Readiness status `not_ready`
fails the smoke run.

## Common Failures And Fixes

| Failure | Likely Cause | Fix |
| --- | --- | --- |
| `/health` request fails | API service is down or URL is wrong | Verify deployment URL and API process |
| readiness `not_ready` | Database, Redis, storage, or required config failed | Inspect `/api/v1/health/readiness` checks |
| auth login fails | Smoke user password does not match existing account | Reset the staging smoke account password |
| usage returns 401 | Token issue or auth service problem | Re-run auth step and inspect API logs |
| reel creation returns 402 | Smoke workspace hit usage limits | Use a fresh smoke account or upgrade in test billing |
| render times out | Rendering worker or FFmpeg unavailable | Check rendering queue, worker logs, and FFmpeg |
| mock Stripe skipped | Staging does not expose development routes | This is expected for normal staging |
| mock Instagram skipped | Staging does not expose development routes | This is expected for normal staging |
