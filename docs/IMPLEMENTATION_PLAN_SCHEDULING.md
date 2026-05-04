# Implementation Plan: Scheduling + Publish Queue

## 1. Database & Model Updates
*   **Enum Updates**: Add `SCHEDULED`, `RECONNECT_REQUIRED` to `PublishJobStatus` to safely align with existing statuses while fulfilling scheduling requirements.
*   **PublishJob Table**: Add the following columns:
    *   `queued_at` (DateTime)
    *   `locked_at` (DateTime)
    *   `cancelled_at` (DateTime)
    *   `cancel_reason` (String)
    *   `schedule_timezone` (String)
    *   `execution_attempts` (Integer, default 0)
    *   `next_attempt_at` (DateTime)
*   **Migration**: Generate Alembic migration for the schema changes.

## 2. API Endpoints
*   `POST /api/v1/reel-projects/{project_id}/schedule`: Validate inputs (future date > 2 mins, correct workspace, rendered video available), create `PublishJob` with status `SCHEDULED`.
*   `DELETE /api/v1/publish-jobs/{publish_job_id}/schedule`: Cancel a scheduled job (if status is `SCHEDULED`).
*   `PUT /api/v1/publish-jobs/{publish_job_id}/schedule`: Reschedule a job (if status is `SCHEDULED`).

## 3. Worker Scheduler
*   Implement `scan_scheduled_publish_jobs` task.
*   This task queries for `PublishJob` where `status == SCHEDULED` and `scheduled_for <= now()`.
*   Uses `locked_at` to ensure idempotency.
*   Moves job to `QUEUED` and dispatches the existing `publish_reel_task`.
*   Celery Beat will be configured to run this periodically.

## 4. Frontend Integration
*   Update `api-client.ts` with new scheduling interfaces and methods.
*   Update `/dashboard/reels/[id]/page.tsx` to include "Schedule Publish" functionality, allowing date/time input.
*   Display scheduled jobs distinctly in the jobs timeline, showing cancellation and reschedule options.

## 5. Testing & Quality Checks
*   Verify API validations.
*   Verify Celery Beat configuration.
*   Run `ruff` and `pytest`.
*   Run `npm run lint`.
