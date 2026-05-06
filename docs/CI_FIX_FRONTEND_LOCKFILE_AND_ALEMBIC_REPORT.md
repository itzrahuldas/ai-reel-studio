# CI Fix Report: Frontend Lockfile And Alembic Revisions

**Branch:** `fix/ci-frontend-lockfile-and-alembic-revisions`
**Date:** 2026-05-06

## Summary

This patch fixes the two current GitHub Actions failures without changing
product behavior:

- Frontend `npm ci` now uses a lockfile regenerated from `apps/web/package.json`.
- Alembic migration revision identifiers that exceeded 32 characters were
  shortened before staging/production adoption.

## Frontend Root Cause

The frontend CI job was already running from `apps/web`, but
`apps/web/package-lock.json` was stale. The lockfile had an invalid `picomatch`
resolution relationship, which made `npm ci` reject the install.

## Frontend Fix

Ran `npm install` from `apps/web` to regenerate the lockfile, then verified
`npm ci`, lint, typecheck, and build from the same directory used by CI.

## Backend Root Cause

Alembic's default `alembic_version.version_num` column is `VARCHAR(32)`.
The revision id `0003_update_social_account_fields` is 33 characters, so fresh
Postgres migration runs failed when Alembic attempted to write it.

## Alembic Revision IDs Changed

| Previous ID | New ID |
| --- | --- |
| `0003_update_social_account_fields` | `0003_social_account_fields` |
| `0004_add_reel_version_editor_fields` | `0004_reel_editor_fields` |
| `0005_add_scheduling_publish_job_fields` | `0005_scheduling_fields` |

The existing no-op `0005` bridge remains in the linear chain because it is
already a short revision id and preserves the current `0006` down-revision path.
All revision and down-revision values are now 32 characters or fewer.

## Files Changed

- `.github/workflows/ci.yml`
- `apps/web/package-lock.json`
- `apps/api/alembic/versions/0003_update_social_account_fields.py`
- `apps/api/alembic/versions/0004_add_reel_version_editor_fields.py`
- `apps/api/alembic/versions/0005_add_scheduling_publish_job_fields.py`
- `apps/api/alembic/versions/0005_bridge_legacy_billing_down_revision.py`
- `docs/CHANGELOG.md`
- `docs/CI_FIX_FRONTEND_LOCKFILE_AND_ALEMBIC_REPORT.md`

## Commands Run

```bash
git status --short --branch
git branch --show-current
git remote -v
git log --oneline -8
npm install
npm ci
npm run lint
npm run typecheck
npm run build
python -m compileall app alembic
alembic heads
alembic history --verbose
alembic upgrade head
python -m ruff check app tests
pytest -q
git diff --check
```

## Test Results

- `npm ci`: passed.
- Frontend lint: passed.
- Frontend typecheck: passed after `next build` regenerated stale local
  `.next/types` artifacts.
- Frontend build: passed.
- Backend compileall: passed.
- `alembic heads`: passed, single head `0009`.
- `alembic history --verbose`: passed.
- Backend Ruff: passed.
- Full backend pytest: `77 passed`.
- `alembic upgrade head`: blocked locally by missing Postgres
  (`ConnectionRefusedError` to `localhost:5432`). GitHub Actions provides the
  required Postgres service.

## Remaining Risks

- Local frontend install reports existing npm audit advisories, including a
  Next.js advisory. Upgrading app dependencies is outside this CI repair scope.
- Local Alembic upgrade could not be executed because Postgres is unavailable in
  this shell, but CI runs with a fresh Postgres service.

## GitHub Actions Expectation

GitHub Actions should now pass the previous failing points:

- Frontend dependency install should pass because `package-lock.json` is synced.
- Alembic upgrade should no longer fail on revision id length because every
  migration revision id in the chain fits `VARCHAR(32)`.
