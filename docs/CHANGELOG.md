# Changelog — AI Reel Studio

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Staging deployment setup artifacts: `.env.staging.example`,
  `docker-compose.staging.yml`, staging deploy/migration scripts, and staging
  deployment plan/checklist docs.
- Staging smoke test script, manual GitHub Actions smoke workflow, and API
  liveness/readiness/config health endpoints for deployment verification.
- Real AI Provider Integration Phase 1 with mock/OpenAI creative planning, image analysis, TTS voiceover generation, timed subtitle alignment, and FFmpeg voiceover rendering.
- Stripe subscription billing with hosted Checkout, Customer Portal, webhook lifecycle processing, and development mock mode.
- Stripe webhook event idempotency/audit table and Stripe provider fields on workspace subscriptions.
- Credits, Plans, and Usage Limits hardening with retry-safe usage events.
- Usage idempotency indexes and publish job payload columns in migration `0007`.
- Frontend usage-limit handling with billing CTAs for create, regenerate, render, publish, schedule, and editor render flows.
- Production-grade monorepo scaffold (`ai-reel-studio/`)
- Full documentation suite (PRODUCT_SPEC, ARCHITECTURE, SYSTEM_WORKFLOW, DATABASE_SCHEMA, API_REFERENCE, INSTAGRAM_INTEGRATION, AI_PIPELINE, VIDEO_RENDERING, SECURITY, DEPLOYMENT, ROADMAP)
- Architecture Decision Records (ADR-0001, ADR-0002, ADR-0003)
- Antigravity agent system (12 agent personas, 10 skill files, 6 workflow files)
- FastAPI backend skeleton with all models, schemas, routers, and service stubs
- Next.js 15 frontend skeleton with all pages, components, and API client
- Celery worker with all task skeletons
- AI provider abstraction (LLM, Vision, Video, TTS, Mock providers)
- FFmpeg renderer service with subtitle and audio support
- Instagram OAuth and publishing integration skeleton
- Docker Compose with all services (web, api, worker, postgres, redis, minio)
- GitHub Actions CI pipeline (frontend lint/typecheck + backend lint/tests)
- GitHub issue templates and PR template
- `.env.example` with all required variables
- Helper scripts (setup.sh, dev.sh, test.sh, lint.sh)
- SQLAlchemy models for all 11 database tables
- Alembic migration skeleton
- Prompt templates (reel_planner.md, caption_generator.md, moderation.md)
- CONTRIBUTING.md, SECURITY.md, LICENSE

### Fixed
- Fixed workspace plan enum storage mismatch that broke staging registration.
- Pinned bcrypt below v5 for passlib compatibility in Docker staging auth.
- Repaired structlog's stdlib logger configuration so Docker staging startup
  logging no longer crashes and sensitive log fields remain redacted.
- Synced the frontend package lockfile so `npm ci` installs from `apps/web`
  cleanly in CI.
- Shortened pre-staging Alembic revision identifiers so every `version_num`
  value fits Alembic's default 32-character version table column.
- Enforced `PUBLISH` usage when scheduled publish jobs actually execute.
- Made `consume_usage()` check idempotency before quota and use `used + quantity > limit`.
- Moved publish URL validation and schedule time validation before usage writes.
- Created default FREE subscriptions for additional workspace creation.
- Added SQLAlchemy foreign-key disambiguation for workspace memberships.

---

## [0.1.0] - 2026-05-03

### Added
- Initial project bootstrap
- Complete folder structure established
- All documentation stubs created

[Unreleased]: https://github.com/your-org/ai-reel-studio/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/your-org/ai-reel-studio/releases/tag/v0.1.0

## [0.2.0] - 2026-05-03
### Added
- **Backend Auth:** Full JWT authentication lifecycle (/register, /login, /me, /logout).
- **Workspaces:** Multi-tenant isolation with workspace generation on signup.
- **Database Migrations:** Alembic initialized and configured for async autogeneration.
- **Frontend Pages:** Real integrations on /login, /register, and /dashboard/settings.
