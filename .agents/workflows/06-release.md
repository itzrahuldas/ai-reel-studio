# Workflow 05: GitHub Sync

## Trigger
Run this workflow when ready to push changes to GitHub.

## Steps

### 1. Check Git Status
`ash
git status
git diff --stat
`

### 2. Create Branch (if needed)
`ash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/your-bug-description
`

### 3. Stage Meaningful Files
`ash
git add apps/ packages/ services/ docs/ .github/ scripts/
git add docker-compose.yml .env.example README.md
# Do NOT add: .env, node_modules/, __pycache__/, .venv/
`

### 4. Create Descriptive Commit
`ash
git commit -m "feat(api): implement reel generation pipeline

- Add GenerationJob model and Celery task
- Add LLM provider abstraction with OpenAI + mock
- Add image analysis integration
- Add output validation against CreativePlanSchema
- Update IMPLEMENTATION_LOG.md and CHANGELOG.md

Closes #42"
`

### 5. Update CHANGELOG.md
Ensure changelog entry exists for this change.

### 6. Push
`ash
git push -u origin feat/your-feature-name
`

### 7. Create PR
If GitHub MCP tools are available:
- Create PR with title following: 	ype(scope): description
- Fill in PR template
- Assign reviewers

If GitHub MCP tools are NOT available, print:
`ash
# Create PR manually at: https://github.com/your-org/ai-reel-studio/compare
# Or use GitHub CLI:
gh pr create --title "feat(api): implement reel generation pipeline" --body "..."
`
"@ | Set-Content "c:\Users\Rahul\work_vid\ai-reel-studio\.agents\workflows\05-github-sync.md"

# Workflow 06
@"
# Workflow 06: Release

## Trigger
Run this workflow when releasing a new version.

## Pre-Release Checklist
- [ ] All tests passing (run Workflow 04)
- [ ] No critical security issues open
- [ ] CHANGELOG.md updated
- [ ] All required env variables documented in .env.example
- [ ] Migrations tested (upgrade + downgrade)

## Steps

### 1. Verify Tests
`ash
bash scripts/test.sh
`

### 2. Update Version
- Update version in pps/api/pyproject.toml
- Update version in pps/web/package.json
- Update version in root README.md status table

### 3. Update Changelog
Move items from [Unreleased] to new version section:
`markdown
## [0.2.0] - 2026-MM-DD
### Added
...
### Fixed
...
`

### 4. Create Git Tag
`ash
git tag -a v0.2.0 -m "Release v0.2.0: Beta launch"
git push origin v0.2.0
`

### 5. Create Release Notes
Document in GitHub Releases:
- Summary of what's new
- Breaking changes (if any)
- How to upgrade
- Known issues

### 6. Deployment Checklist
- [ ] Run lembic upgrade head on staging
- [ ] Deploy API + worker to staging
- [ ] Deploy frontend to staging
- [ ] Smoke test all critical flows
- [ ] Run lembic upgrade head on production
- [ ] Deploy to production
- [ ] Monitor error rates for 30 minutes
