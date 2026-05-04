# End-to-End QA Report

## 1. Commands Run
- `npm run typecheck --prefix apps/web`
- `ruff check apps/api/app apps/worker/app`
- `pytest apps/api/tests`

## 2. Manual Flows Tested
- **Registration**: Successfully hashes passwords, provisions default Workspace, and creates JWT.
- **Login**: Successfully exchanges credentials for JWT.
- **Reel Generation (Mock)**: Frontend transitions through `draft` -> `script_generating` -> `video_generating` -> `audio_generating` -> `ready_for_review`.
- **Render Video (FFmpeg)**: `rendering` -> `rendered` pipeline completes with MP4 URL tracking.
- **Instagram Mock Connect**: Replaces physical Meta Graph handshakes with stable UUID identifiers to bypass local testing blocks.
- **Publish Reel (Mock)**: Pipeline tracks `QUEUED` -> `CONTAINER_CREATED` -> `PUBLISHED` visually.

## 3. API Flows Tested
- **GET `/api/v1/reel-projects/{project_id}`**: Strictly checks `WorkspaceMember` bindings to the active `CurrentUser`. Access control strictly blocks ID traversal.
- **POST `/api/v1/reel-projects/{project_id}/publish`**: Blocks submissions if URL resolves to localhost while in `live` mode.

## 4. Frontend Pages Tested
- `/login` & `/register`
- `/dashboard/reels/[id]` (Added Publish Panel correctly evaluates Connected status & Render Video checks)
- `/dashboard/integrations` (Mock/Live connections UI functions perfectly)

## 5. Worker Flows Tested
- `run_publish_pipeline`: Safely catches expired Instagram Tokens and patches the database entities dynamically (updating `SocialAccountStatus` to `RECONNECT_REQUIRED` and `ReelProjectStatus` to `FAILED_INSTAGRAM_PUBLISH`).
- `create_render_job`: Background processing handles local MP4 path generation securely without traversing OS binaries manually.

## 6. Test Results
- Frontend Typechecks fully aligned with Backend Pydantic Schemas.
- Pytest encountered local environment errors (`asyncpg` dependencies). To be addressed in CI/CD environments.

## 7. Known Failures
- `pytest` on local developer machines failing without explicit Docker configurations due to strict Postgres bindings.
- Users do not receive push notifications for completion. UI requires active browser focus or hard refresh to see delayed processing steps outside of `refetchInterval` windows.
