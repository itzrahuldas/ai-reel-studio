# Feature Report: Instagram Reels Publish Pipeline

## Summary
Implemented the Instagram Reels Publish Pipeline allowing authenticated users to publish rendered MP4 reels directly to a connected Instagram Professional account via the Meta Graph API. The pipeline supports both asynchronous Celery worker execution (for live production) and synchronous execution (for mock/development environments).

## User Workflow Implemented
1. User logs in.
2. User connects Instagram account (or uses mock connect).
3. User navigates to `/dashboard/reels/{project_id}` after rendering a video.
4. An Instagram Publishing section is now available, showing connected accounts.
5. User clicks "Publish to Feed".
6. A `publish_job` is created and the pipeline starts executing in the background.
7. The status updates in real-time in the new Publish History timeline (QUEUED -> CONTAINER_CREATED -> POLLING -> PUBLISHED).
8. If the publish fails, a "Retry" button is available.
9. If a token is expired, a "Fix Connection" button links the user back to the integrations page.

## API Endpoints Implemented
- **POST `/api/v1/reel-projects/{project_id}/publish`**: Creates a new publish job and enqueues the publish pipeline execution.
- **GET `/api/v1/reel-projects/{project_id}/publish-jobs`**: Retrieves the history of publish jobs for the reel project.
- **POST `/api/v1/reel-projects/publish-jobs/{job_id}/retry`**: Retries a failed publish job.

## Publish Job Behavior
The publish pipeline uses a robust Celery task that executes in the following steps:
1. Validates input payload and checks if the project already reached terminal state.
2. Authenticates and establishes an Instagram Graph API client session.
3. Creates a media container (`ig_container_id` stored).
4. Polls the Meta Graph API for container processing status.
5. Upon `FINISHED`, publishes the media (`ig_media_id` stored) and marks the job as `PUBLISHED`.

## Instagram Media Container Behavior
Meta requires a two-step process:
1. Container creation: Supplying video URL and caption.
2. Polling: The container processing status takes up to 1-3 minutes.
3. Publish: Marking the processed container as published on the user's feed.

## Mock Mode Behavior
When `INSTAGRAM_INTEGRATION_MODE=mock`:
- Localhost URLs are permitted.
- The pipeline bypasses the Instagram Meta Graph client completely.
- A simulated 2-second container creation followed by a 3-second processing delay replicates the live environment behavior before marking the job as successful with a mock URL.

## Public URL Validation Behavior
Live mode requires a publicly accessible HTTPS URL. If `API_PUBLIC_BASE_URL` or the configured storage domain resolves to `localhost` or `127.0.0.1` while in live mode, the backend returns a `400 Bad Request` automatically blocking invalid submissions before they reach the Meta API.

## Token/Security Behavior
Raw tokens are **never logged** and only decrypted at runtime within the Celery worker task using `TOKEN_ENCRYPTION_KEY`. Any Meta Graph API errors that suggest token invalidity automatically map the user's connection status to `RECONNECT_REQUIRED`.

## Frontend Changes
- Integrated `publishReelProject`, `getPublishJobs`, `retryPublishJob` directly into `api-client.ts`.
- Augmented the `ReelDetailPage` component (`page.tsx`) with an Instagram publishing panel.
- Included robust polling mechanisms linked directly with Tanstack Query `refetchInterval`.

## Commands Run
- `git checkout -b feature/instagram-reels-publish-pipeline`
- `ruff check --fix apps/api/app apps/worker/app`
- `npm run typecheck --prefix apps/web`

## Test Results
- Frontend Typecheck: 100% Passed.
- Automatic backend format/lint: Passed.

## Known Gaps
- Currently does not support scheduled publishings natively in the UI (backend models support `scheduled_for` for a future date).
- We rely on the frontend timeline to visualize publish progress, but no email notifications are sent upon publish completion.

## Risks
- Polling the Meta Graph API is subject to standard rate limits, but exponential backoff isn't fully utilized internally for container polling.

## Recommended Next Feature
- **Advanced Timeline Editor**: A unified drag-and-drop reel timeline view that enables modifying the script text, subtitles, and scene duration dynamically, allowing granular customization prior to rendering the final MP4.
