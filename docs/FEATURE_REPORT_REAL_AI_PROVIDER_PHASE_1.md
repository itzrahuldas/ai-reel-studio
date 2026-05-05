# Feature Report: Real AI Provider Integration Phase 1

## 1. Summary

Real AI Provider Integration Phase 1 adds production-ready provider abstractions
for creative planning, image analysis, TTS voiceover generation, and timed
subtitle alignment. Mock mode remains the default for local development, and
OpenAI mode can be enabled independently for planning, image analysis, and TTS.

Phase 1 does not add real AI video providers. FFmpeg rendering remains the
video output path.

## 2. Provider Architecture

The backend now exposes provider interfaces for:

- `CreativePlannerProvider`
- `ImageAnalysisProvider`
- `TTSProvider`
- `SubtitleTimingProvider`

Provider selection is centralized in `app/services/ai/provider_factory.py`.
Schemas and validation helpers live in `app/services/ai/schemas.py`.

## 3. OpenAI Configuration

OpenAI providers are selected with:

- `AI_PROVIDER=openai`
- `IMAGE_ANALYSIS_PROVIDER=openai`
- `TTS_PROVIDER=openai`

Required server secret:

- `AI_API_KEY`

Optional model/runtime settings:

- `AI_MODEL`
- `IMAGE_ANALYSIS_MODEL`
- `TTS_MODEL`
- `TTS_VOICE`
- `AI_REQUEST_TIMEOUT_SECONDS`
- `AI_MAX_RETRIES`
- `AI_GENERATION_TEMPERATURE`

If any OpenAI provider is selected without `AI_API_KEY`, the API returns a clear
503 setup error before usage is consumed.

## 4. Mock Mode Behavior

Mock mode remains the default and performs no external calls. The mock image
provider returns fixture visual context, the mock planner returns a validated
creative plan, and the mock TTS provider writes valid silent WAV audio so render
and preview flows can be tested locally.

## 5. Generation Pipeline

Generation now runs as:

1. Validate provider setup before usage consumption.
2. Consume the existing `AI_GENERATION` usage unit with job idempotency.
3. Resolve the uploaded source image.
4. Analyze the image through the selected image provider.
5. Generate a structured Pydantic creative plan from prompt, image analysis,
   language, tone, duration, CTA, and brand inputs.
6. Save hook, script, storyboard, caption, hashtags, video prompt, moderation
   flags, and timed subtitle JSON.
7. Generate TTS voiceover when text is available.
8. Store generated voiceover as an `audio` media asset.
9. Align subtitle timings to voiceover duration when possible.
10. Store safe provider metadata and mark the version ready for review.

## 6. TTS Behavior

TTS failures are handled conservatively. In development/mock flows, generation
can continue without voiceover and stores a warning. In production with OpenAI
TTS selected, TTS failure marks the generation failed with a sanitized error.

TTS does not consume a separate credit in Phase 1. The existing `AI_GENERATION`
unit covers planning, image analysis, subtitles, and TTS.

## 7. Render Integration

Render jobs now resolve `reel_versions.voiceover_asset_id` or `audio_asset_id`.
When audio exists, FFmpeg includes it in the MP4. When no audio exists, the
existing silent-audio fallback remains in place.

## 8. Database Changes

Migration `0009_add_real_ai_provider_fields.py` adds:

- `reel_versions.voiceover_asset_id`
- `generation_jobs.provider`
- `generation_jobs.provider_metadata_json`
- `generation_jobs.error_code`

## 9. API/Schema Changes

New authenticated endpoint:

- `GET /api/v1/reel-projects/ai/provider-status`

Updated response schemas include:

- `ReelVersionResponse.voiceover_asset_id`
- `ReelVersionResponse.audio_asset_id`
- `ReelVersionResponse.edit_metadata`
- `GenerationJobResponse.provider`
- `GenerationJobResponse.provider_metadata_json`
- `GenerationJobResponse.error_code`

## 10. Security Notes

- `AI_API_KEY` is never exposed to the frontend.
- Provider errors are sanitized before storage/display.
- The provider status endpoint returns mode/configuration state only.
- Full prompts and API keys are not logged by provider code.
- Mock mode remains safe for local development.

## 11. Commands Run

- `git status --short --branch`
- `git branch --show-current`
- `git remote -v`
- `git log --oneline -5`
- `git switch -c feature/real-ai-provider-phase-1`
- `python -m compileall app`
- `pytest tests/unit/test_ai_provider_phase1.py --no-cov -q`
- `python -m ruff check app/services/ai/base.py app/services/ai/mock_provider.py app/services/ai/schemas.py app/services/ai/provider_factory.py app/services/ai/openai_provider.py`
- `npm run typecheck`
- `npm run lint`
- `alembic heads`
- `alembic history -r "0007:head"`
- `python -m py_compile app/tasks/generate_reel.py`
- `docker compose config`
- `pytest --no-cov -q --tb=no`

## 12. Test Results

- Targeted AI provider backend tests: passing, 9 passed.
- AI provider module ruff check: passing.
- Frontend typecheck: passing.
- Frontend lint: passing with one pre-existing `@next/next/no-img-element`
  warning on the reel detail page.
- Alembic heads: single head `0009`.
- Alembic history shows `0007 -> 0008 -> 0009`.
- Worker task syntax validation with `py_compile`: passing.
- `docker compose config`: not available locally because Docker CLI is not
  installed on this machine.

Full backend pytest completed with legacy failures outside this feature:
65 passed, 12 failed. Failures were in existing auth/reel project tests due
invalid fixture UUIDs, local PostgreSQL connection refusals, and legacy worker
task expectations.

## 13. Known Gaps

- Real AI video generation is still intentionally deferred.
- OpenAI responses are unit-tested through provider construction and schema
  validation, not live API calls.
- TTS duration is estimated from text length unless the provider exposes exact
  timing metadata.
- Local worker import validation is affected by the existing monorepo `app`
  package name collision; the generation task syntax is preserved and the API
  sends Celery tasks by name.

## 14. Risks

- OpenAI model response formats may evolve; Pydantic validation fails safely but
  may require prompt/schema tuning.
- Production TTS failures fail generation when OpenAI TTS is selected, which is
  safer but may need user-facing retry controls later.
- Audio file storage must be backed by persistent local/S3-compatible storage in
  deployed environments.

## 15. Next Recommended Feature

Real AI Provider Integration Phase 2: add live provider observability, cost
tracking, retry controls, and optional transcript-level TTS timing before adding
real AI video providers.
