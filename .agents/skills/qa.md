# Skill: QA

## Unit Test Rules
- Test each service method independently
- Mock all external dependencies (DB, S3, AI providers, Instagram API)
- Use pytest fixtures for common setup
- One test file per module: 	ests/unit/test_{module}.py
- Test both happy path and error paths
- Minimum: 1 happy path + 2 error/edge cases per service method

## Integration Test Rules
- Test API endpoints end-to-end (HTTP request ? DB)
- Use TestClient from FastAPI
- Use a test database (separate from dev DB)
- Reset DB state between tests using transactions + rollback
- Mock all external APIs (AI providers, Instagram API, S3)
- One test file per router: 	ests/integration/test_{router}_router.py

## E2E Test Rules (Playwright)
- Tests live in pps/web/tests/e2e/
- Use Page Object Model pattern
- Test critical user flows: create reel, approve, connect Instagram
- Run against local Docker Compose stack
- Screenshot on failure

## Bug Reproduction Rule
Before fixing any bug:
1. Write a failing test that reproduces the bug
2. Confirm the test fails (red)
3. Fix the bug
4. Confirm the test passes (green)
5. Add to regression suite

## Regression Test Rule
- Every bug fix must include a regression test
- Regression tests tagged @pytest.mark.regression
- Regression suite runs on every PR
