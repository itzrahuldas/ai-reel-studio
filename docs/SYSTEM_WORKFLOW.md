# System Workflow — AI Reel Studio

**Version:** 0.1.0
**Last Updated:** 2026-05-03

---

## 1. End-to-End User Flow

```
1. User lands on / (landing page)
2. User logs in → /login
3. User goes to /dashboard
4. User clicks "Create Reel" → /dashboard/create
5. User fills form:
   - Text prompt / business idea
   - Uploads image (JPEG/PNG/WEBP, max 20MB)
   - Optional: language, tone, duration, CTA text
6. User submits → POST /api/v1/reel-projects
7. API returns project_id + pre-signed S3 upload URL
8. Browser uploads image directly to S3
9. Browser calls PATCH /api/v1/reel-projects/{id}/start-generation
10. User is redirected to /dashboard/reels/{id}
11. Page polls status via GET /api/v1/reel-projects/{id}
12. User sees live status updates as generation progresses
13. When READY_FOR_REVIEW:
    - User sees: script, storyboard, caption, hashtags, video preview
    - User can edit caption/hashtags
    - User can approve or reject
14. If approved → POST /api/v1/publish-jobs
15. User sees publishing status until PUBLISHED or FAILED
```

---

## 1.1 Billing Workflow

```
Workspace starts on FREE
  -> user opens /dashboard/billing
  -> frontend loads GET /api/v1/billing/plans and /usage
  -> user clicks Upgrade for CREATOR or PRO
  -> API creates Stripe Checkout Session in subscription mode
  -> Stripe redirects user through hosted Checkout
  -> Stripe webhook updates workspace_subscriptions
  -> UsageService reads the effective plan for limit checks
  -> user manages payment/cancel/plan changes through Stripe Customer Portal
```

Paid limits are effective only while subscription status is `active` or
`trialing`. Canceled, unpaid, past-due, and incomplete subscriptions fall back
to `FREE` limits for enforcement while preserving billing status for the UI.

---

## 2. Internal Generation Flow

```
POST /api/v1/reel-projects
  → validate request (Zod/Pydantic)
  → create User (if new) + Workspace
  → create ReelProject (status: DRAFT)
  → create MediaAsset record (status: PENDING_UPLOAD)
  → generate S3 pre-signed URL
  → return {project_id, upload_url}

PATCH /api/v1/reel-projects/{id}/start-generation
  → verify image uploaded to S3 (HEAD request)
  → update MediaAsset (status: UPLOADED)
  → update ReelProject (status: SCRIPT_GENERATING)
  → create GenerationJob (status: QUEUED)
  → enqueue Celery: generate_creative_plan_task(job_id)
  → return {job_id, status}

[Worker] generate_creative_plan_task
  → load GenerationJob from DB
  → fetch image bytes from S3
  → call ImageAnalysisProvider.analyze(image_bytes)
  → build prompt from packages/prompts/reel_planner.md
  → call LLMProvider.generate(prompt)
  → validate JSON output: {hook, script, scenes, voiceover_text, 
                            subtitle_lines, caption, hashtags, 
                            video_prompt, moderation_flags, 
                            estimated_duration_seconds}
  → run moderation check on moderation_flags
  → create ReelVersion (status: SCRIPT_READY)
  → update GenerationJob (status: SCRIPT_COMPLETE)
  → update ReelProject (status: SCRIPT_READY)
  → enqueue: generate_audio_task(version_id)
  → enqueue: generate_video_task(version_id)  [or skip if FFmpeg fallback]

[Worker] generate_audio_task
  → load ReelVersion
  → call TTSProvider.synthesize(voiceover_text, language, voice)
  → upload audio .mp3 to S3
  → create MediaAsset (type: AUDIO)
  → update GenerationJob audio_status: AUDIO_COMPLETE
  → check if video also complete → trigger render_reel_task if so

[Worker] generate_video_task  [AI video provider]
  → call VideoProvider.generate(video_prompt, image_url, duration)
  → poll for completion
  → download video
  → upload raw video to S3
  → create MediaAsset (type: RAW_VIDEO)
  → update GenerationJob video_status: VIDEO_COMPLETE
  → check if audio also complete → trigger render_reel_task if so

  [Fallback if VideoProvider fails or not configured]
  → log warning: using FFmpeg fallback renderer
  → skip to render_reel_task directly with static image

[Worker] render_reel_task
  → update ReelVersion (status: RENDERING)
  → load image, audio (optional), subtitle_lines from DB/S3
  → call FFmpegRenderer.render(...)
  → output: 1080x1920 MP4, thumbnail.jpg, metadata.json
  → upload all to S3
  → update ReelVersion (status: READY_FOR_REVIEW, asset URLs)
  → update ReelProject (status: READY_FOR_REVIEW)
  → create RenderJob record (COMPLETE)
```

---

## 3. Review / Approval Flow

```
GET /api/v1/reel-projects/{id}
  → returns full project + latest version data
  → frontend renders: script, storyboard cards, caption, hashtags
  → frontend renders: <VideoPreview> with S3 signed URL

User edits caption/hashtags:
  PATCH /api/v1/reel-versions/{version_id}/caption
  PATCH /api/v1/reel-versions/{version_id}/hashtags

User approves:
  POST /api/v1/reel-versions/{version_id}/approve
  → update ReelVersion (status: APPROVED)
  → update ReelProject (status: APPROVED)

User rejects / requests regeneration:
  POST /api/v1/reel-versions/{version_id}/reject
  → update ReelVersion (status: REJECTED)
  → update ReelProject (status: DRAFT)
  → optionally enqueue new generation with updated prompt
```

---

## 4. Publishing Flow

```
POST /api/v1/publish-jobs
  body: { project_id, social_account_id, schedule_time? }

  → verify ReelProject.status == APPROVED
  → verify SocialAccount.status == CONNECTED
  → verify SocialAccount token not expired
  → create PublishJob (status: QUEUED)
  → enqueue: publish_reel_task(publish_job_id)

[Worker] publish_reel_task
  → load PublishJob + ReelVersion + SocialAccount
  → get S3 public URL for rendered MP4
  → call InstagramClient.create_media_container(
      ig_user_id, video_url, caption, share_to_feed=True
    )
  → receive container_id
  → update PublishJob (status: CONTAINER_CREATED, container_id)
  → enqueue: poll_instagram_status_task(publish_job_id)

[Worker] poll_instagram_status_task
  → load PublishJob
  → call InstagramClient.check_container_status(container_id)
  → if status == FINISHED:
      → call InstagramClient.publish_media(ig_user_id, container_id)
      → receive ig_media_id
      → update PublishJob (status: PUBLISHED, ig_media_id)
      → update ReelProject (status: PUBLISHED)
      → write AuditLog entry
  → if status == ERROR:
      → update PublishJob (status: FAILED_INSTAGRAM_PUBLISH, error_msg)
      → update ReelProject (status: FAILED_INSTAGRAM_PUBLISH)
      → write AuditLog entry
  → if status == IN_PROGRESS:
      → re-enqueue poll after 10s (max 20 retries = ~3 min)
```

---

## 5. Usage Idempotency and Retry Safety

Expensive actions are checked and consumed in the API or worker only after request validation and job creation:

- create/generate and regenerate create a `GenerationJob`, flush it, then consume `AI_GENERATION`
- render creates a `RenderJob`, flushes it, then consumes `RENDER`
- publish now validates project, rendered video, social account, token preflight, and public URL, then creates a `PublishJob` and consumes `PUBLISH`
- schedule validates project, rendered video, social account, public URL, and schedule time before creating a scheduled `PublishJob`
- scheduled publish creation records a `SCHEDULED_PUBLISH` event and occupies an active schedule slot
- scheduled publish execution consumes monthly `PUBLISH` quota when the publish pipeline starts

`related_job_id` is the usage event idempotency key. Retries of the same generation, render, publish, or scheduled publish job do not double-charge because `consume_usage()` checks for an existing usage event before quota checks or counter increments.

If scheduled publish execution is blocked by monthly publish quota, the worker does not call Meta, marks the publish job failed with `USAGE_LIMIT_EXCEEDED`, and leaves the project/version ready to publish.

Public HTTPS video URL validation happens before publish usage is consumed in live mode.

---

## 6. Failure & Retry Flow

```
[Worker] Task failure handling:
  → Celery retry with exponential backoff: [10s, 30s, 90s, 270s]
  → Max retries: 3 (configurable per task)
  → On final failure:
      → update GenerationJob/RenderJob/PublishJob (status: FAILED)
      → update ReelProject (status: FAILED_*)
      → write AuditLog entry with error details
      → mark task as non-retryable

[API] Failure query:
  → GET /api/v1/reel-projects/{id}
  → returns status: FAILED_*, latest_error_message, retry_available: bool

[Frontend] Failure UI:
  → show error state with human-readable message
  → show "Retry" button if retry_available
  → POST /api/v1/reel-projects/{id}/retry
      → resets status → DRAFT → re-enqueues generation task

[Instagram token expiry]:
  → Worker detects OAuthException code 190
  → update SocialAccount (status: RECONNECT_REQUIRED)
  → update PublishJob (status: FAILED, error: TOKEN_EXPIRED)
  → frontend: /dashboard/integrations shows "Reconnect" banner
  → user re-initiates OAuth flow
```
