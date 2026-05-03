# Workflow 04: Test and Fix

## Trigger
Run this workflow after implementing a feature or when tests are failing.

## Steps

### 1. Run Lint
`ash
# Backend
cd apps/api && ruff check .
cd apps/api && ruff format --check .

# Frontend
cd apps/web && npm run lint
`

### 2. Run Typecheck
`ash
cd apps/web && npm run typecheck
cd apps/api && mypy app/ --ignore-missing-imports
`

### 3. Run Unit Tests
`ash
cd apps/api && pytest tests/unit/ -v
`

### 4. Run Integration Tests
`ash
cd apps/api && pytest tests/integration/ -v
`

### 5. Run Frontend Tests
`ash
cd apps/web && npm run test
`

### 6. Fix Issues
- Fix lint errors first (usually fastest)
- Fix type errors next
- Fix failing tests last
- Never suppress errors with # noqa or // eslint-disable without comment explaining why

### 7. Update TEST_REPORT.md
Record in docs/TEST_REPORT.md (create if not exists):
- Date run
- Pass/fail counts
- Any known failures with ticket references
- Coverage percentage if available
