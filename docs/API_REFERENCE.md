# API Reference — AI Reel Studio

**Version:** 0.1.0
**Base URL:** `http://localhost:8000/api/v1`
**Auth:** Bearer JWT token in `Authorization` header

---

## Authentication

All endpoints except `/health` and `/api/v1/auth/*` require:
```
Authorization: Bearer <access_token>
```

---

## Error Response Shape

All errors return:
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Reel project not found",
    "request_id": "req_abc123",
    "details": {}
  }
}
```

**Error Codes:**
| Code                   | HTTP Status | Description                    |
|------------------------|-------------|--------------------------------|
| VALIDATION_ERROR       | 422         | Request body validation failed |
| UNAUTHORIZED           | 401         | Missing or invalid token       |
| FORBIDDEN              | 403         | Insufficient permissions       |
| RESOURCE_NOT_FOUND     | 404         | Entity not found               |
| CONFLICT               | 409         | State conflict (e.g. already published) |
| RATE_LIMITED           | 429         | Too many requests              |
| INTERNAL_ERROR         | 500         | Unexpected server error        |
| SERVICE_UNAVAILABLE    | 503         | Upstream dependency failure    |

---

## Endpoints

### Health
```
GET /health
Response 200: { "status": "ok", "version": "0.1.0", "timestamp": "..." }
```

### Auth
```
POST /api/v1/auth/register
Body: { email, password, full_name }
Response 201: { user_id, email, access_token }

POST /api/v1/auth/login
Body: { email, password }
Response 200: { access_token, token_type: "bearer", expires_in: 3600 }

POST /api/v1/auth/refresh
Body: { refresh_token }
Response 200: { access_token, expires_in }

POST /api/v1/auth/logout
Response 200: { message: "logged out" }
```

### Workspaces
```
GET  /api/v1/workspaces              → list user's workspaces
POST /api/v1/workspaces              → create workspace
GET  /api/v1/workspaces/{id}         → get workspace
PATCH /api/v1/workspaces/{id}        → update workspace
GET  /api/v1/workspaces/{id}/members → list members
POST /api/v1/workspaces/{id}/members → invite member
DELETE /api/v1/workspaces/{id}/members/{user_id} → remove member
```

### Social Accounts
```
GET  /api/v1/social-accounts                         → list connected accounts
POST /api/v1/social-accounts/instagram/connect       → initiate OAuth (returns auth_url)
GET  /api/v1/social-accounts/instagram/callback      → OAuth callback handler
DELETE /api/v1/social-accounts/{id}                  → disconnect account
POST /api/v1/social-accounts/{id}/reconnect          → re-initiate OAuth for expired token
```

### Media Assets
```
POST /api/v1/media-assets/upload-url
Body: { filename, mime_type, file_size, project_id? }
Response 201: { asset_id, upload_url, expires_at }

PATCH /api/v1/media-assets/{id}/confirm-upload
Response 200: { asset_id, status: "uploaded" }

GET /api/v1/media-assets/{id}
Response 200: { asset_id, s3_key, signed_url, status, ... }
```

### Reel Projects
```
GET  /api/v1/reel-projects                    → list projects (paginated)
POST /api/v1/reel-projects                    → create project
GET  /api/v1/reel-projects/{id}               → get project + latest version
PATCH /api/v1/reel-projects/{id}              → update project settings
DELETE /api/v1/reel-projects/{id}             → soft delete
PATCH /api/v1/reel-projects/{id}/start-generation → trigger AI generation
POST /api/v1/reel-projects/{id}/retry         → retry failed generation
```

### Reel Versions
```
GET  /api/v1/reel-versions/{id}               → get version detail
PATCH /api/v1/reel-versions/{id}/caption      → update caption
PATCH /api/v1/reel-versions/{id}/hashtags     → update hashtags
POST /api/v1/reel-versions/{id}/approve       → approve for publishing
POST /api/v1/reel-versions/{id}/reject        → reject version
```

### Generation Jobs
```
GET /api/v1/generation-jobs/{id}              → get job status + logs
```

### Publish Jobs
```
POST /api/v1/publish-jobs
Body: { project_id, social_account_id, schedule_time? }
Response 201: { job_id, status }

GET  /api/v1/publish-jobs/{id}               → get publish job status
POST /api/v1/publish-jobs/{id}/cancel        → cancel pending job
```

---

## Request/Response Contracts (Key Examples)

### POST /api/v1/reel-projects
```json
Request:
{
  "workspace_id": "uuid",
  "prompt": "Launch post for my bakery's new sourdough line",
  "language": "en",
  "tone": "warm",
  "duration_seconds": 30,
  "cta_text": "Order now at mybakery.com"
}

Response 201:
{
  "id": "uuid",
  "status": "draft",
  "title": "Bakery Sourdough Reel",
  "upload_url": "https://s3.amazonaws.com/...",
  "asset_id": "uuid",
  "created_at": "2026-05-03T10:00:00Z"
}
```

### GET /api/v1/reel-projects/{id}
```json
Response 200:
{
  "id": "uuid",
  "status": "ready_for_review",
  "title": "Bakery Sourdough Reel",
  "prompt": "...",
  "latest_version": {
    "id": "uuid",
    "version_number": 1,
    "hook": "Your morning just got better ☕",
    "script": "...",
    "scenes": [...],
    "caption": "Introducing our new Sourdough collection...",
    "hashtags": ["#sourdough", "#bakery", "#fresh"],
    "estimated_duration": 30,
    "rendered_video_url": "https://signed-s3-url...",
    "thumbnail_url": "https://signed-s3-url...",
    "status": "ready_for_review"
  },
  "created_at": "...",
  "updated_at": "..."
}
```

### POST /api/v1/publish-jobs
```json
Request:
{
  "project_id": "uuid",
  "social_account_id": "uuid"
}

Response 201:
{
  "id": "uuid",
  "status": "queued",
  "created_at": "..."
}
```
