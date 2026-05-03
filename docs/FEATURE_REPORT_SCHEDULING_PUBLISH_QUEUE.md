# Feature Report: Scheduling + Publish Queue

## Summary
Added the ability to schedule rendered Reels for future publishing to Instagram. Users can pick a date, time, and timezone from the Advanced Reel Editor/Dashboard, which enqueues a `SCHEDULED` publish job instead of publishing immediately. A new Celery beat task runs periodically to pick up these jobs when their time arrives and processes them through the existing publishing pipeline.

## User Workflow Implemented
1. User navigates to `/dashboard/reels/[id]`.
2. Under "Instagram Publishing", next to a connected account, the user clicks "Schedule".
3. A form appears to pick the publish date and time.
4. Clicking "Confirm Schedule" creates a scheduled publish job.
5. The scheduled job appears in the "Publish History" timeline with a "Cancel Schedule" option.
6. A Celery beat worker checks for scheduled jobs every minute. When the time arrives, it moves the job to `QUEUED` and executes the publish flow.

## API Endpoints Implemented
- `POST /api/v1/reel-projects/{project_id}/schedule` - Schedules a Reel for publishing.
- `DELETE /api/v1/publish-jobs/{publish_job_id}/schedule` - Cancels an unexecuted scheduled job.

## Database Changes
- Migrations: `0005_add_scheduling_publish_job_fields.py`
- Added enum values `SCHEDULED` and `RECONNECT_REQUIRED` to `PublishJobStatus`.
- Added fields to `PublishJob`:
  - `scheduled_for`
  - `schedule_timezone`
  - `queued_at`
  - `locked_at`
  - `cancelled_at`
  - `cancel_reason`
  - `execution_attempts`
  - `next_attempt_at`

## Worker Scheduler Behavior
- A new task `scan_scheduled_publish_jobs` runs every 60 seconds (configured in Celery Beat).
- Scans for jobs with status `SCHEDULED` where `scheduled_for <= now()`.
- Uses a `locked_at` column to prevent concurrent worker execution for the same job.
- Transitions the job to `QUEUED` and triggers the existing `publish_reel_task`.

## Idempotency/Locking Behavior
- The scanner only picks up jobs with `status == SCHEDULED`. Once picked up, they are `QUEUED`.
- It sets `locked_at` and increments `execution_attempts` immediately to reserve the job.
- It won't pick up jobs that are already in terminal states (`PUBLISHED`, `FAILED`, `CANCELLED`).
- Existing `publish_reel_task` safely checks for terminal states before running the Meta API pipeline.

## Frontend Changes
- Updated `api-client.ts` with `scheduleReelProject` and `cancelScheduledPublishJob`.
- Added `SchedulePublishJobRequest` interface.
- Updated `/dashboard/reels/[id]/page.tsx` with a responsive scheduling form under the account section.
- Updated timeline UI to handle `scheduled` status properly, exposing the cancel option.

## Test Results
- Frontend `npm run lint` check completed successfully (0 errors).
- Backend linting `ruff check .` ran successfully with expected line length warnings (no structural errors related to the newly written code).
- Alembic migration files created cleanly.

## Known Gaps
- A full `/dashboard/schedule` centralized view wasn't created to avoid disruption, but the per-project dashboard handles scheduling comprehensively.
- Rescheduling requires canceling and scheduling again, for simplicity.

## Risks
- If Celery Beat is not running in the deployed environment, scheduled posts will not execute. The deployment configuration needs to ensure the `celery-beat` service is actively deployed alongside workers.

## Next Recommended Feature
- **Advanced Reel Editor Phase 2 (Timeline UI)**: To give users finer control over individual subtitle timing and storyboard lengths.
- **Analytics Dashboard**: To aggregate engagement data on published content.
