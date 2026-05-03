# Feature Report: Real FFmpeg Video Rendering Pipeline

## Objective
Implement a production-grade FFmpeg-based video rendering pipeline that transforms AI-generated content (images, script, subtitles) into a cohesive 9:16 vertical MP4 video, fully integrated with the Celery queue and Next.js frontend.

## Implementation Details

### 1. Backend Orchestration (`render_service.py`)
- Created a centralized service to orchestrate the rendering lifecycle, mapping a `ReelVersion` to a `RenderJob`.
- Respects the `GENERATION_MODE` setting, dynamically enqueuing a Celery task in `async` mode or running synchronously for local development (`sync`).
- Robust handling of media assets: securely retrieves local storage paths without exposing them to the frontend and provides URL wrappers (`build_media_url`) that serve via the `/static` API mount.
- Generates a `creative_plan` structure that aligns seamlessly with the `FFmpegRenderer` interface.

### 2. FFmpeg Integration (`ffmpeg_renderer.py`)
- Standardized the core renderer to accept configuration for `background_image_path`, `subtitle_srt_path`, and optional audio.
- Employs dynamic "Ken Burns" (zoompan) motion for static images to provide a video-like experience.
- Implemented subtitle burn-in using FFmpeg's `subtitles` filter with strict absolute path handling, escaping Windows paths to prevent FFmpeg crashes.
- Automatically generates a companion JPEG thumbnail by extracting the first frame of the finished video.

### 3. Database Schema Updates (`models.py` & Alembic)
- Expanded the `ReelProjectStatus` enum to track rendering states: `RENDERING`, `RENDERED`, and `READY_TO_PUBLISH`.
- Enhanced the `RenderJob` model to include `project_id`, `input_payload` (configuration sent to FFmpeg), and `output_payload` (resulting paths and dimensions) for enhanced debugging and auditability.
- Created `alembic/versions/0002_add_render_job_fields.py` to persist schema changes.

### 4. Celery Worker (`render_reel.py`)
- Completed the `render_reel_task` by wiring it directly into the `render_service.py` async pipeline via `asyncio.run()`.
- Implemented robust error catching that safely registers a `FAILED_RENDER` state if FFmpeg encounters an error.

### 5. Frontend Integration (`page.tsx` & `api-client.ts`)
- Upgraded TanStack Query endpoints to fetch and poll `render-jobs`.
- Embedded a new "Render Video" action on the reel detail page that securely transitions the project state to `rendering`.
- Enhanced the dashboard preview panel: it natively renders the HTML5 `<video>` tag with the generated thumbnail as the `poster` when rendering succeeds.
- Introduced a dedicated `RenderTimeline` component mapping `queued`, `running`, `complete`, and `failed` jobs.

## Known Gaps & Future Enhancements
- **Audio Synthesis**: The current implementation does not yet execute Text-To-Speech (TTS) integration, running the video silently if `background_audio_path` is missing. Future iterations should wire TTS outputs into the `audio_path`.
- **Cloud Storage**: The `media_assets.py` router and `render_service.py` are heavily optimized for `local` storage via FastApi `StaticFiles`. The transition to S3 (production) requires injecting pre-signed URLs in `build_media_url`.

## Verification Status
- Validated TypeScript checks (`npm run typecheck`).
- Pytest API coverage expanded to cover render endpoints and pipeline execution.
- Idempotency confirmed for Celery tasks.
