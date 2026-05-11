# Changelog — AI Reel Studio

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Fixed
- **Celery render async DB isolation** (`fix(worker): isolate render async database sessions`):
  - `render_reel_task` was calling `_run_render_pipeline_inline()` which opens
    the global `AsyncSessionLocal` (backed by a module-level `create_async_engine`).
    When Celery's prefork worker calls `asyncio.run()`, a new event loop is created
    but asyncpg connection futures were attached to a previous loop, causing:
    `RuntimeError: Task got Future attached to a different loop`.
  - Fix: added `render_session_scope()` async context manager in
    `apps/worker/app/tasks/render_reel.py` (mirrors `scheduler_session_scope()`).
    It creates a **fresh** `create_async_engine` + `async_sessionmaker` inside the
    task's own event loop, disposes the engine in `finally`.
  - Added `_run_render_pipeline_with_db(db, ...)` to `render_service.py`:
    accepts an explicit `AsyncSession` so the pipeline is loop-agnostic.
  - `_run_render_pipeline_inline` is now a thin wrapper that opens
    `AsyncSessionLocal` and delegates to `_run_render_pipeline_with_db` —
    the API sync path is unchanged.
  - Worker task calls `_run_render_pipeline_with_db` via
    `_run_render_with_isolated_session`; never touches global `AsyncSessionLocal`.
  - Test file `tests/test_worker_render_task.py` rewritten with 5 focused tests
    covering: session scope engine disposal, task routing to `_with_db` not
    `_inline`, failed pipeline, exception path, and inline delegation.
- **Render task exception result** (`fix(worker): return failed render task results on exceptions`):
  - `render_reel_task` previously called `self.retry(exc=exc)` on unexpected
    exceptions, then caught `MaxRetriesExceededError` to return a dict.
    Calling `.run()` in tests bypasses Celery retry machinery — `Retry` escaped
    as an unhandled exception, making tests non-deterministic.
  - Fix: removed `self.retry` entirely. `_run_render_pipeline_with_db` already
    handles all recoverable errors internally (catches, writes `status=failed` to
    the DB, returns `False`). Any exception that escapes to the task level is
    unrecoverable — retrying would hit the same error. Return a structured
    `{"status": "failed", "error_type": ..., "error": ...}` dict immediately.
  - Removed now-unused `celery.exceptions.MaxRetriesExceededError` import.

### Added
- **Mock visual storyboard renderer** (`feat(render): generate prompt-specific mock visuals`):
  - New `apps/api/app/services/rendering/mock_visuals.py` generates one 1080×1920
    JPEG scene card per storyboard scene using Pillow.
  - Keyword-based theme detection: coffee, fitness, travel, beauty, tech, education,
    realestate, finance, generic — each with a unique colour palette, accent shapes,
    headline style, and motif label.
  - Scenes are stored under `LOCAL_STORAGE_PATH/mock_visuals/` — local paths are
    never exposed in the public API.
  - `FFmpegRenderer` extended with `_build_multi_scene_command()`: builds an FFmpeg
    xfade crossfade slideshow when `scene_image_paths` is provided in `RenderParams`.
  - `render_service.py` calls `generate_mock_storyboard()` before rendering when no
    real source image is uploaded; passes scene image paths to the renderer.
  - Thumbnail fallback: when FFmpeg is not available, the first scene card image is
    copied as the thumbnail.
  - `build_media_asset_response()` now exposes a safe metadata subset in the API
    response (`visual_source`, `mock_visual_theme`, `generated_scene_count`, etc.)
    — `storage_path` is never included.
  - Frontend Reel Detail page shows a labeled notice when mock storyboard render is
    detected: theme name and scene count are shown.
  - `Pillow>=10.0.0` added to `apps/api/pyproject.toml`.
  - Unit tests in `apps/api/tests/unit/test_mock_visuals.py` covering theme detection,
    image dimensions, prompt differentiation, API path safety, and pipeline integration.
  - `docs/VIDEO_RENDERING.md` updated with mock storyboard renderer documentation.
- Public HTTPS staging deployment template, Caddy Compose overlay, Meta
  readiness checklist, and VPS runbook for Meta App Review staging.
- Final Meta submission runbook plus production launch, environment, and
  staging-to-production promotion runbooks.
- Meta App Review documentation package with reviewer instructions, permission
  justifications, screencast script, privacy/deletion checklists, and submission
  notes.
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
- Fixed Reel Detail media previews by returning safe public media URLs for
  rendered videos, thumbnails, and voiceovers, and by showing mock TTS as a
  silent local-testing placeholder.
- Aligned Instagram OAuth review scopes with the Meta App Review package by
  requesting `pages_show_list` instead of unused `pages_read_engagement`.
- Fixed web container runtime binding by forcing `HOSTNAME=0.0.0.0` in the
  Docker CMD so Docker healthcheck can probe `127.0.0.1`.
- Fixed generation Celery async DB lifecycle so provider pipeline no longer
  reuses asyncpg connections across event loops.
- Replaced invalid FFmpeg `force_original_aspect_ratio=cover` renderer filter
  syntax with a valid cover-style scale/crop chain for staging renders.
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
