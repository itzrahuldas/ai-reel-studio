# Post-Stripe Repository Hygiene Report

Date: 2026-05-05
Branch: `feature/stripe-subscription-billing`
Stripe baseline commit: `33a4d95469c8f4da2dd0a633652c45ea7e63bc5c`

## Files Inspected

- `.gitignore`
- `apps/api/app/api/v1/routers/reel_projects.py`
- `apps/api/app/integrations/instagram/oauth.py`
- `apps/web/tsconfig.tsbuildinfo`
- `docs/CREDITS_USAGE_AUDIT_NOTES.md`

## What Was Committed

Planned safe hygiene commit contents:

- `.gitignore`: added `*.tsbuildinfo` so future TypeScript incremental build caches are ignored.
- `apps/api/app/api/v1/routers/reel_projects.py`: preserved a formatting-only import ordering change.
- `apps/api/app/integrations/instagram/oauth.py`: preserved a formatting-only trailing whitespace cleanup.
- `docs/CREDITS_USAGE_AUDIT_NOTES.md`: preserved the credits usage audit notes as historical project documentation.
- `docs/POST_STRIPE_REPO_HYGIENE_REPORT.md`: recorded this hygiene pass.

## What Was Ignored

- Future `*.tsbuildinfo` files are now covered by `.gitignore`.
- Existing generated folders and caches remain ignored, including `node_modules/`, `.next/`,
  `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `dist/`, and `build/`.

## What Remains Uncommitted

- `apps/web/tsconfig.tsbuildinfo`

Reason: this is generated TypeScript incremental build cache. It is already tracked in Git, so `.gitignore`
cannot hide the current modification without untracking or reverting the file. This pass intentionally did
not delete, untrack, or revert it.

## Inspection Notes

- `reel_projects.py` diff was import ordering only.
- `instagram/oauth.py` diff was trailing whitespace cleanup only.
- `docs/CREDITS_USAGE_AUDIT_NOTES.md` contains useful audit history from the credits usage limits work and
  is worth preserving rather than deleting.
- `apps/web/tsconfig.tsbuildinfo` contains TypeScript compiler cache JSON and should not be committed as
  part of this hygiene pass.

## Commands Run

- `git status --short --branch`
- `git diff --stat`
- `git diff -- apps/api/app/api/v1/routers/reel_projects.py`
- `git diff -- apps/api/app/integrations/instagram/oauth.py`
- `git diff -- docs/CREDITS_USAGE_AUDIT_NOTES.md`
- `git status --ignored --short`
- `git ls-files apps/web/tsconfig.tsbuildinfo`
- `git check-ignore -v --no-index apps/web/tsconfig.tsbuildinfo`
- `python -m ruff check app/api/v1/routers/reel_projects.py app/integrations/instagram/oauth.py`
- `python -m ruff check app/integrations/instagram/oauth.py`
- `npm run typecheck`
- `git diff --check`

## Quality Gate Results

- Frontend typecheck: passed.
- `git diff --check`: passed.
- Ruff on `apps/api/app/integrations/instagram/oauth.py`: passed.
- Ruff on both touched Python files: failed due existing issues in `reel_projects.py`
  (`ANN401`, `E402`, and `E501`) outside the hygiene scope.

## Latest Commit Hash

- Latest commit before this hygiene report: `33a4d95469c8f4da2dd0a633652c45ea7e63bc5c`
- Final pushed hygiene commit hash should be read from `git log -1` after this report is committed.

## Safe For Next Feature

Yes, with one caveat: `apps/web/tsconfig.tsbuildinfo` remains a tracked generated file with an uncommitted
local modification. It was intentionally preserved and not staged.
