# Workflow 02: Implement Feature

## Trigger
Run this workflow when implementing any new feature or significant change.

## Pre-Flight Checks
1. Read docs/PRODUCT_SPEC.md — verify feature is in scope
2. Read docs/ARCHITECTURE.md — understand service boundaries
3. Read the nearest IMPLEMENTATION_LOG.md — understand current state
4. Read relevant API_CONTRACT.md if touching an integration
5. Identify which agent persona(s) own this work

## Steps

### 1. Plan
- Write a brief technical plan (5–10 bullet points)
- Identify affected files
- Identify new files to create
- Identify tests to write
- Confirm no architectural violations

### 2. Implement
- Follow the relevant skill file conventions
- Add TypeScript types / Pydantic schemas first
- Implement service layer before route layer (backend)
- Implement API client before components (frontend)
- Add error handling and logging throughout

### 3. Test
- Write unit tests for new logic
- Write integration test for new API endpoint (if applicable)
- Verify existing tests still pass
- Add to TEST_PLAN.md

### 4. Document
- Update nearest IMPLEMENTATION_LOG.md with what was done
- Update docs/CHANGELOG.md with entry
- Update docs/API_REFERENCE.md if endpoint changed
- Update docs/DATABASE_SCHEMA.md if model changed
- Create ADR if architectural decision was made

### 5. Quality Gate
`ash
# Backend
cd apps/api && ruff check . && pytest

# Frontend
cd apps/web && npm run lint && npm run typecheck
`

### 6. Commit Summary
Prepare a commit message:
`
feat(scope): short description

- bullet point 1
- bullet point 2

Refs: #issue-number
`
"@ | Set-Content "c:\Users\Rahul\work_vid\ai-reel-studio\.agents\workflows\02-implement-feature.md"

# Workflow 03
@"
# Workflow 03: Code Review

## Trigger
Run this workflow before merging any PR or significant change.

## Steps

### 1. Read Changed Files
- List all changed files
- Understand the scope of the change

### 2. Architecture Check
- Does this change respect service boundaries?
- Does this introduce any circular dependencies?
- Does this require an ADR?

### 3. Code Quality Check
- Are all types explicit (no ny in TypeScript, no bare except in Python)?
- Is error handling complete?
- Are logs structured and correlation-ID-aware?
- Are there TODO comments that should be filed as issues?

### 4. Security Check
- Are any secrets potentially exposed?
- Is file upload validation present if handling files?
- Are rate limits applied to new public endpoints?
- Are audit logs written for sensitive operations?

### 5. Test Coverage Check
- Do new services have unit tests?
- Do new endpoints have integration tests?
- Are edge cases covered?

### 6. Documentation Check
- Is IMPLEMENTATION_LOG.md updated?
- Is CHANGELOG.md updated?
- Are API_REFERENCE.md / DATABASE_SCHEMA.md updated if needed?

### 7. Produce Report
Create REVIEW_REPORT.md in the PR or scratch directory:
- Files reviewed
- Issues found (critical / warning / suggestion)
- Approval recommendation (approve / request changes / needs discussion)
