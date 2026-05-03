# Feature Report: Advanced Reel Editor (Phase 1)

## Overview
Phase 1 of the Advanced Reel Editor implements a structured, version-controlled editing workflow for AI-generated reels. It allows users to modify auto-generated components (hook, script, storyboard, voiceover, subtitles, captions, hashtags, and duration) without regenerating the entire project.

## Architecture

### Database Models
- `ReelVersion` model updated with:
  - `render_settings` (JSONB): To store manual overrides such as `duration_seconds`.
  - `edit_metadata` (JSONB): To track specific editing actions/metadata if necessary.

### Services & Logic
- **Editor Service** (`app/services/editor_service.py`):
  - Fetches editable state and capabilities (can edit, render, publish).
  - Handles the saving of drafts. If a reel version has already been rendered, it automatically creates a clone (version bump) to ensure published/rendered artifacts remain unaltered.
- **Render Service**:
  - Updated to accept a specific `version_id`.
  - The render pipeline now reads from `version.render_settings` (e.g., target duration) to override default project settings.

### API Routes
- `GET /api/v1/reel-projects/{project_id}/editor`: Returns editor configuration and constraints.
- `PUT /api/v1/reel-projects/{project_id}/versions/{version_id}`: Saves edits to the current draft or safely branches a new version.
- `POST /api/v1/reel-projects/{project_id}/versions/{version_id}/clone`: Manually triggers a version clone.

### Frontend
- **Editor UI** (`/dashboard/reels/[id]/edit`):
  - Two-column layout separating metadata (script, hook, captions) from granular timeline aspects (storyboard scenes, subtitle lines).
  - Real-time save and render actions.
- **Detail View**:
  - Includes an "Edit Reel" button dynamically disabled while the system is generating or rendering.

## Quality Checks
- Frontend linting and type-checking fully pass.
- Backend schemas validated using Pydantic.
- Editor API robustly guarded against mutation of published reels.

## Future Phases
- Phase 2 will introduce an interactive, Final Cut-style timeline UI for precision editing.
- Integration of real TTS editing and audio wave visualization.
