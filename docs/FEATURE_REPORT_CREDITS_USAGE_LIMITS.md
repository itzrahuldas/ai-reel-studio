# Feature Report: Credits, Plans, and Usage Limits

**Date:** 2026-05-04
**Branch:** `feature/credits-usage-limits`
**Status:** Implemented and hardened for Stripe readiness

---

## Summary

Credits, Plans, and Usage Limits are now enforced at the backend execution points that spend real platform capacity:

- AI generation for create and regenerate flows
- FFmpeg render job creation
- publish-now job creation
- active scheduled publish slot creation
- scheduled publish execution when the actual publish pipeline starts

The feature remains plan-definition driven. The current static plans are:

| Plan | AI generations/month | Renders/month | Publishes/month | Active scheduled publishes | Watermark |
|---|---:|---:|---:|---:|---|
| FREE | 5 | 3 | 2 | 1 | enabled |
| CREATOR | 50 | 30 | 30 | 20 | disabled |
| PRO | 200 | 150 | 150 | 100 | disabled |

---

## Usage Idempotency and Retry Safety

`related_job_id` is the idempotency key for usage events. `UsageService.consume_usage()` now checks for an existing `(workspace_id, event_type, related_job_id)` event before it checks quota or increments counters. A retry of the same job returns safely and does not double-charge usage.

The enforced job keys are:

- Create/generate reel: `GenerationJob.id` with `AI_GENERATION`
- Regenerate reel: new `GenerationJob.id` with `AI_GENERATION`
- Render reel: `RenderJob.id` with `RENDER`
- Publish now: `PublishJob.id` with `PUBLISH`
- Schedule publish: `PublishJob.id` with `SCHEDULED_PUBLISH`
- Scheduled publish execution: same `PublishJob.id` with `PUBLISH`

Scheduled jobs consume active schedule slot capacity when the schedule is created. They do not consume monthly publish quota until the scheduler hands the job to the publish pipeline and the actual publish attempt starts.

Retries do not double-charge. Public URL validation for live Instagram publishing happens before publish usage is consumed, so invalid local or non-HTTPS media URLs do not spend publish credits.

---

## Enforcement Matrix

| Action | Status | Usage event | Idempotency key |
|---|---|---|---|
| Create/generate Reel | Enforced | `AI_GENERATION` | generation job ID |
| Regenerate Reel | Enforced | `AI_GENERATION` | generation job ID |
| Render Reel | Enforced | `RENDER` | render job ID |
| Publish now | Enforced | `PUBLISH` | publish job ID |
| Schedule publish | Enforced | `SCHEDULED_PUBLISH` | publish job ID |
| Scheduled publish execution | Enforced | `PUBLISH` | publish job ID |

---

## Database Changes

Migration `0007_add_usage_idempotency_constraints.py` adds:

- `publish_jobs.input_payload`
- `publish_jobs.output_payload`
- non-unique lookup indexes for usage counters and usage event idempotency
- unique usage counter period index when duplicate production rows are not present
- partial unique usage event idempotency index when duplicate production rows are not present

The migration does not delete duplicate data. If duplicate rows already exist, the service-layer idempotency remains active and production data cleanup can be handled before enabling unique database protection.

---

## HTTP 402 Contract

Usage limits return HTTP 402 with this payload in `detail`:

```json
{
  "code": "USAGE_LIMIT_EXCEEDED",
  "message": "You have reached your monthly publish limit.",
  "plan_key": "FREE",
  "limit": 2,
  "used": 2,
  "upgrade_required": true
}
```

The frontend accepts the payload either as the top-level response body or under `detail`.

---

## Validation Notes

Focused backend unit tests cover usage service idempotency, quantity enforcement, workspace subscription creation, publish validation timing, schedule validation timing, and scheduled usage event creation.

The broader endpoint suite still requires local PostgreSQL/Redis services and has older mocked response-shape assumptions. Those failures are tracked separately from this usage enforcement patch.
