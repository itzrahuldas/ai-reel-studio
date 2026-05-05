# Database Schema — AI Reel Studio

**Version:** 0.1.0
**Last Updated:** 2026-05-03

---

## 1. Tables Overview

| Table               | Description                                    |
|---------------------|------------------------------------------------|
| `users`             | Platform user accounts                         |
| `workspaces`        | Tenant/team containers                         |
| `workspace_members` | User → Workspace membership + roles            |
| `social_accounts`   | Connected Instagram accounts                   |
| `media_assets`      | S3-referenced files (images, video, audio)     |
| `reel_projects`     | Top-level reel project container               |
| `reel_versions`     | Individual generation versions of a project    |
| `generation_jobs`   | AI content generation job tracking             |
| `render_jobs`       | FFmpeg render job tracking                     |
| `publish_jobs`      | Instagram publishing job tracking              |
| `workspace_subscriptions` | Workspace plan and billing period state  |
| `usage_counters`    | Monthly usage counters per workspace/period    |
| `usage_events`      | Immutable usage audit and idempotency events   |
| `stripe_webhook_events` | Stripe webhook audit and idempotency events |
| `audit_logs`        | Immutable event log for all sensitive actions  |

---

## 2. Field Definitions

### `users`
| Column          | Type         | Notes                              |
|-----------------|--------------|-------------------------------------|
| id              | UUID PK      | gen_random_uuid()                   |
| email           | VARCHAR(320) | UNIQUE NOT NULL                     |
| hashed_password | VARCHAR(255) | bcrypt                              |
| full_name       | VARCHAR(255) |                                     |
| is_active       | BOOLEAN      | default TRUE                        |
| is_verified     | BOOLEAN      | default FALSE                       |
| created_at      | TIMESTAMPTZ  | server_default=now()                |
| updated_at      | TIMESTAMPTZ  | auto-updated via trigger            |

### `workspaces`
| Column      | Type         | Notes                    |
|-------------|--------------|--------------------------|
| id          | UUID PK      |                          |
| name        | VARCHAR(255) | NOT NULL                 |
| slug        | VARCHAR(100) | UNIQUE NOT NULL          |
| owner_id    | UUID FK      | → users.id               |
| plan        | VARCHAR(50)  | 'free'/'pro'/'agency'    |
| is_active   | BOOLEAN      | default TRUE             |
| created_at  | TIMESTAMPTZ  |                          |
| updated_at  | TIMESTAMPTZ  |                          |

### `workspace_members`
| Column       | Type        | Notes                              |
|--------------|-------------|------------------------------------|
| id           | UUID PK     |                                    |
| workspace_id | UUID FK     | → workspaces.id ON DELETE CASCADE  |
| user_id      | UUID FK     | → users.id ON DELETE CASCADE       |
| role         | VARCHAR(50) | 'owner'/'admin'/'member'/'viewer'  |
| invited_by   | UUID FK     | → users.id NULLABLE               |
| joined_at    | TIMESTAMPTZ |                                    |
| created_at   | TIMESTAMPTZ |                                    |
| updated_at   | TIMESTAMPTZ |                                    |

### `social_accounts`
| Column                 | Type          | Notes                                    |
|------------------------|---------------|------------------------------------------|
| id                     | UUID PK       |                                          |
| workspace_id           | UUID FK       | → workspaces.id                          |
| user_id                | UUID FK       | → users.id (who connected it)            |
| platform               | VARCHAR(50)   | 'instagram' (expandable)                 |
| platform_user_id       | VARCHAR(255)  | IG user ID                               |
| platform_username      | VARCHAR(255)  | @handle                                  |
| platform_page_id       | VARCHAR(255)  | FB Page ID (required for IG API)         |
| access_token_encrypted | TEXT          | AES-256 encrypted                        |
| token_expires_at       | TIMESTAMPTZ   | NULLABLE                                 |
| status                 | VARCHAR(50)   | 'connected'/'reconnect_required'/'error' |
| scopes                 | TEXT[]        | granted OAuth scopes                     |
| created_at             | TIMESTAMPTZ   |                                          |
| updated_at             | TIMESTAMPTZ   |                                          |

### `media_assets`
| Column       | Type         | Notes                                        |
|--------------|--------------|----------------------------------------------|
| id           | UUID PK      |                                              |
| workspace_id | UUID FK      | → workspaces.id                              |
| project_id   | UUID FK      | → reel_projects.id NULLABLE                  |
| version_id   | UUID FK      | → reel_versions.id NULLABLE                  |
| asset_type   | VARCHAR(50)  | 'source_image'/'raw_video'/'audio'/'rendered_video'/'thumbnail' |
| s3_key       | TEXT         | S3 object key                                |
| s3_bucket    | VARCHAR(255) | bucket name                                  |
| filename     | VARCHAR(500) | original or generated filename               |
| mime_type    | VARCHAR(100) |                                              |
| file_size    | BIGINT       | bytes                                        |
| status       | VARCHAR(50)  | 'pending_upload'/'uploaded'/'processing'/'ready'/'error' |
| metadata     | JSONB        | extra metadata (dimensions, duration, etc.)  |
| created_at   | TIMESTAMPTZ  |                                              |
| updated_at   | TIMESTAMPTZ  |                                              |

### `reel_projects`
| Column           | Type         | Notes                                 |
|------------------|--------------|---------------------------------------|
| id               | UUID PK      |                                       |
| workspace_id     | UUID FK      | → workspaces.id                       |
| created_by       | UUID FK      | → users.id                            |
| title            | VARCHAR(500) | auto-generated or user-set            |
| prompt           | TEXT         | user's original text prompt           |
| language         | VARCHAR(20)  | BCP-47 code e.g. 'en', 'hi', 'es'    |
| tone             | VARCHAR(100) | 'professional'/'casual'/'energetic'   |
| duration_seconds | INTEGER      | target reel duration                  |
| cta_text         | VARCHAR(500) | optional call-to-action text          |
| status           | VARCHAR(50)  | see state machine                     |
| latest_version_id| UUID FK      | → reel_versions.id NULLABLE           |
| source_image_id  | UUID FK      | → media_assets.id NULLABLE            |
| created_at       | TIMESTAMPTZ  |                                       |
| updated_at       | TIMESTAMPTZ  |                                       |

### `reel_versions`
| Column               | Type        | Notes                                   |
|----------------------|-------------|-----------------------------------------|
| id                   | UUID PK     |                                         |
| project_id           | UUID FK     | → reel_projects.id                      |
| version_number       | INTEGER     | incremented per project                 |
| hook                 | TEXT        | opening hook line                       |
| script               | TEXT        | full voiceover script                   |
| scenes               | JSONB       | array of scene objects                  |
| voiceover_text       | TEXT        |                                         |
| subtitle_lines       | JSONB       | timed subtitle entries                  |
| caption              | TEXT        | Instagram caption                       |
| hashtags             | TEXT[]      |                                         |
| video_prompt         | TEXT        | AI video generation prompt              |
| estimated_duration   | INTEGER     | seconds                                 |
| moderation_flags     | JSONB       | any content flags from AI               |
| voiceover_asset_id   | UUID FK     | → media_assets.id NULLABLE, generated TTS voiceover |
| audio_asset_id       | UUID FK     | → media_assets.id NULLABLE              |
| video_asset_id       | UUID FK     | → media_assets.id NULLABLE              |
| rendered_asset_id    | UUID FK     | → media_assets.id NULLABLE              |
| thumbnail_asset_id   | UUID FK     | → media_assets.id NULLABLE              |
| status               | VARCHAR(50) | see state machine                       |
| approved_by          | UUID FK     | → users.id NULLABLE                     |
| approved_at          | TIMESTAMPTZ |                                         |
| rejection_reason     | TEXT        |                                         |
| created_at           | TIMESTAMPTZ |                                         |
| updated_at           | TIMESTAMPTZ |                                         |

### `generation_jobs`
| Column          | Type        | Notes                                   |
|-----------------|-------------|-----------------------------------------|
| id              | UUID PK     |                                         |
| project_id      | UUID FK     | → reel_projects.id                      |
| version_id      | UUID FK     | → reel_versions.id NULLABLE             |
| celery_task_id  | VARCHAR(255)| Celery task UUID                        |
| job_type        | VARCHAR(50) | 'full_generation'/'script_only'         |
| status          | VARCHAR(50) | 'queued'/'running'/'complete'/'failed'  |
| started_at      | TIMESTAMPTZ |                                         |
| completed_at    | TIMESTAMPTZ |                                         |
| error_message   | TEXT        |                                         |
| retry_count     | INTEGER     | default 0                               |
| input_payload   | JSONB       | full input snapshot                     |
| output_payload  | JSONB       | full output snapshot                    |
| provider        | VARCHAR(50) | mock/openai provider used for generation |
| provider_metadata_json | JSONB | safe provider metadata, no secrets       |
| error_code      | VARCHAR(100)| sanitized machine-readable failure code |
| created_at      | TIMESTAMPTZ |                                         |
| updated_at      | TIMESTAMPTZ |                                         |

### `render_jobs`
| Column         | Type        | Notes                     |
|----------------|-------------|---------------------------|
| id             | UUID PK     |                           |
| version_id     | UUID FK     | → reel_versions.id        |
| celery_task_id | VARCHAR(255)|                           |
| status         | VARCHAR(50) | queued/running/complete/failed |
| renderer       | VARCHAR(50) | 'ffmpeg'/'ai_video'       |
| started_at     | TIMESTAMPTZ |                           |
| completed_at   | TIMESTAMPTZ |                           |
| error_message  | TEXT        |                           |
| command_log    | TEXT        | sanitized ffmpeg command  |
| created_at     | TIMESTAMPTZ |                           |
| updated_at     | TIMESTAMPTZ |                           |

### `publish_jobs`
| Column            | Type        | Notes                           |
|-------------------|-------------|---------------------------------|
| id                | UUID PK     |                                 |
| project_id        | UUID FK     | → reel_projects.id              |
| version_id        | UUID FK     | → reel_versions.id              |
| social_account_id | UUID FK     | → social_accounts.id            |
| celery_task_id    | VARCHAR(255)|                                 |
| status            | VARCHAR(50) | queued/container_created/published/failed |
| ig_container_id   | VARCHAR(255)| Meta container ID               |
| ig_media_id       | VARCHAR(255)| Published IG media ID           |
| scheduled_for     | TIMESTAMPTZ | NULLABLE = publish immediately  |
| started_at        | TIMESTAMPTZ |                                 |
| published_at      | TIMESTAMPTZ |                                 |
| error_message     | TEXT        |                                 |
| retry_count       | INTEGER     | default 0                       |
| created_at        | TIMESTAMPTZ |                                 |
| updated_at        | TIMESTAMPTZ |                                 |

### `audit_logs`
| Column       | Type        | Notes                                       |
|--------------|-------------|---------------------------------------------|
| id           | UUID PK     |                                             |
| workspace_id | UUID FK     | → workspaces.id NULLABLE                    |
| user_id      | UUID FK     | → users.id NULLABLE (null for system)       |
| action       | VARCHAR(255)| e.g. 'reel.published', 'account.connected'  |
| resource_type| VARCHAR(100)| 'reel_project'/'publish_job'/etc.           |
| resource_id  | UUID        | NULLABLE                                    |
| ip_address   | INET        | NULLABLE                                    |
| user_agent   | TEXT        | NULLABLE                                    |
| metadata     | JSONB       | additional context (no PII, no secrets)     |
| created_at   | TIMESTAMPTZ | NOT NULL — never updated                    |

### `workspace_subscriptions`
| Column                  | Type        | Notes                                  |
|-------------------------|-------------|----------------------------------------|
| id                      | UUID PK     |                                        |
| workspace_id            | UUID FK     | unique workspace subscription row       |
| plan_key                | VARCHAR(50) | `FREE`, `CREATOR`, or `PRO`             |
| status                  | VARCHAR(50) | active/trialing/canceled/past_due/unpaid/incomplete |
| provider                | VARCHAR(50) | manual/stripe/mock_stripe               |
| stripe_customer_id      | VARCHAR(255)| nullable Stripe Customer ID             |
| stripe_subscription_id  | VARCHAR(255)| nullable Stripe Subscription ID         |
| stripe_price_id         | VARCHAR(255)| nullable Stripe Price ID                |
| stripe_checkout_session_id | VARCHAR(255)| last Stripe Checkout Session ID      |
| current_period_start    | TIMESTAMPTZ | monthly billing period start            |
| current_period_end      | TIMESTAMPTZ | monthly billing period end              |
| cancel_at_period_end    | BOOLEAN     | default false                           |
| metadata_json           | JSONB       | provider metadata, no secrets           |
| created_at              | TIMESTAMPTZ |                                        |
| updated_at              | TIMESTAMPTZ |                                        |

### `usage_counters`
| Column                       | Type        | Notes                                  |
|------------------------------|-------------|----------------------------------------|
| id                           | UUID PK     |                                        |
| workspace_id                 | UUID FK     | tenant scope                            |
| period_start                 | TIMESTAMPTZ | monthly usage period start              |
| period_end                   | TIMESTAMPTZ | monthly usage period end                |
| ai_generations_used          | INTEGER     | consumed AI generation units            |
| renders_used                 | INTEGER     | consumed render units                   |
| publishes_used               | INTEGER     | consumed publish units                  |
| scheduled_publishes_created  | INTEGER     | audit counter for schedule creations    |
| created_at                   | TIMESTAMPTZ |                                        |
| updated_at                   | TIMESTAMPTZ |                                        |

Indexes:

- `ix_usage_counters_workspace_period`
- `uq_usage_counters_workspace_period` on `(workspace_id, period_start, period_end)` when existing data has no duplicates

### `usage_events`
| Column              | Type        | Notes                                  |
|---------------------|-------------|----------------------------------------|
| id                  | UUID PK     |                                        |
| workspace_id         | UUID FK     | tenant scope                            |
| user_id             | UUID FK     | nullable actor                          |
| event_type          | VARCHAR(50) | `AI_GENERATION`, `RENDER`, `PUBLISH`, `SCHEDULED_PUBLISH` |
| quantity            | INTEGER     | usage units consumed                    |
| related_project_id  | UUID        | optional context                        |
| related_version_id  | UUID        | optional context                        |
| related_job_id      | VARCHAR     | retry/idempotency key                   |
| metadata_json       | JSONB       | usage audit metadata                    |
| created_at          | TIMESTAMPTZ | event creation time                     |

Indexes:

- `ix_usage_events_workspace_type_job`
- partial `uq_usage_events_workspace_type_job` on `(workspace_id, event_type, related_job_id)` where `related_job_id IS NOT NULL` when existing data has no duplicates

### `stripe_webhook_events`
| Column              | Type        | Notes                                  |
|---------------------|-------------|----------------------------------------|
| id                  | UUID PK     |                                        |
| stripe_event_id     | VARCHAR(255)| unique Stripe event ID                 |
| event_type          | VARCHAR(255)| Stripe event type                      |
| processing_status   | VARCHAR(50) | processing/processed/ignored/failed    |
| processed_at        | TIMESTAMPTZ | nullable completion timestamp          |
| error_message       | TEXT        | sanitized error class or ignore reason |
| payload_json        | JSONB       | Stripe event payload, no secrets       |
| created_at          | TIMESTAMPTZ |                                        |
| updated_at          | TIMESTAMPTZ |                                        |

Indexes:

- `uq_stripe_webhook_events_event_id`
- `ix_stripe_webhook_events_stripe_event_id`
- `ix_stripe_webhook_events_event_type`

---

## 3. Relationships

```
users ────────────────────────── workspace_members ── workspaces
  │                                                       │
  │ created_by                                            │
  └──────────────────────────── reel_projects ───────────┘
                                      │
                                 reel_versions
                                      │
                    ┌─────────────────┼───────────────────┐
                    │                 │                   │
              generation_jobs    render_jobs         publish_jobs
                                                          │
                                                   social_accounts

media_assets ─── reel_projects (source_image_id)
             └── reel_versions (voiceover_asset_id, audio_asset_id, video_asset_id,
                                rendered_asset_id, thumbnail_asset_id)
```

---

## 4. Indexing Strategy

```sql
-- Hot query paths
CREATE INDEX idx_reel_projects_workspace_id ON reel_projects(workspace_id);
CREATE INDEX idx_reel_projects_status ON reel_projects(status);
CREATE INDEX idx_reel_projects_created_by ON reel_projects(created_by);
CREATE INDEX idx_reel_versions_project_id ON reel_versions(project_id);
CREATE INDEX idx_generation_jobs_project_id ON generation_jobs(project_id);
CREATE INDEX idx_generation_jobs_status ON generation_jobs(status);
CREATE INDEX idx_publish_jobs_status ON publish_jobs(status);
CREATE INDEX idx_publish_jobs_social_account_id ON publish_jobs(social_account_id);
CREATE INDEX idx_audit_logs_workspace_id ON audit_logs(workspace_id);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
-- Partial index for active social accounts
CREATE INDEX idx_social_accounts_active ON social_accounts(workspace_id)
  WHERE status = 'connected';
```

---

## 5. Migration Strategy

- Alembic with `--autogenerate` for model changes
- All migrations versioned in `apps/api/alembic/versions/`
- Always test: `alembic upgrade head` + `alembic downgrade -1` in CI
- Never destructive migrations without a feature flag + data migration plan
- Enum changes: add new value first, backfill data, remove old value
- Production: run `alembic upgrade head` before deploying new API version
