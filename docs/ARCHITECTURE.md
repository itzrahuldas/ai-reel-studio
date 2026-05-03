# System Architecture — AI Reel Studio

**Version:** 0.1.0
**Last Updated:** 2026-05-03

---

## 1. System Architecture Diagram

```mermaid
graph TB
    subgraph Client["Client (Browser)"]
        FE["Next.js 15 Frontend\nPort 3000"]
    end

    subgraph API["Backend Services"]
        APIGW["FastAPI\nPort 8000\n/api/v1/*"]
        MW["Middleware\nCorrelation ID\nAuth\nRate Limit"]
    end

    subgraph Workers["Worker Layer"]
        CW["Celery Worker\nGenerate / Render / Publish"]
        CB["Celery Beat\nScheduler"]
    end

    subgraph AI["AI Providers (Abstracted)"]
        LLM["LLM Provider\nScript / Caption / Storyboard"]
        IMG["Image Analysis\nVision Model"]
        VID["Video Provider\nAI-to-Video"]
        TTS["TTS Provider\nVoiceover Audio"]
    end

    subgraph Render["Rendering"]
        FFM["FFmpeg Renderer\nFallback / Primary"]
        SUB["Subtitle Burner"]
        AUD["Audio Mixer"]
    end

    subgraph IG["Instagram Integration"]
        OAUTH["Meta OAuth Flow"]
        IGAPI["Instagram Graph API\nMedia Container\nPublish\nPoll"]
    end

    subgraph Storage["Storage Layer"]
        S3["S3-Compatible Storage\nMinIO (local) / AWS S3 (prod)"]
        PG["PostgreSQL 16\nPrimary Database"]
        RD["Redis\nQueue + Cache"]
    end

    FE -->|REST + JSON| APIGW
    APIGW --> MW
    MW --> APIGW
    APIGW -->|Celery tasks| RD
    RD -->|consume| CW
    CW --> LLM
    CW --> IMG
    CW --> VID
    CW --> TTS
    CW --> FFM
    FFM --> SUB
    FFM --> AUD
    CW --> IGAPI
    OAUTH --> APIGW
    CW -->|read/write| PG
    APIGW -->|read/write| PG
    CW -->|store assets| S3
    FE -->|fetch assets| S3
    CB -->|schedule| RD
```

---

## 2. Service Boundaries

| Service         | Responsibility                                           | Port  |
|-----------------|----------------------------------------------------------|-------|
| `apps/web`      | User interface, routing, state management               | 3000  |
| `apps/api`      | REST API, auth, job dispatch, status queries             | 8000  |
| `apps/worker`   | Async job execution (AI, render, publish)                | N/A   |
| PostgreSQL      | Persistent data: users, projects, jobs, logs             | 5432  |
| Redis           | Celery message broker + result backend + cache           | 6379  |
| S3/MinIO        | Binary asset storage (images, video, audio)              | 9000  |
| Meta Graph API  | Instagram OAuth + Reels publishing (external)            | N/A   |

---

## 3. Data Flow

### 3.1 Project Creation Flow
```
Browser → POST /api/v1/reel-projects
       → API creates ReelProject (DRAFT)
       → API creates MediaAsset record
       → S3 pre-signed upload URL returned
       → Browser uploads image directly to S3
       → Browser PATCH /api/v1/reel-projects/{id}/start-generation
       → API creates GenerationJob (QUEUED)
       → Celery task enqueued → Worker picks up
```

### 3.2 AI Generation Flow
```
Worker: generate_creative_plan_task
  → fetch image from S3
  → image analysis (Vision provider)
  → LLM: generate script/storyboard/caption/hashtags
  → validate JSON output against schema
  → moderation check
  → save ReelVersion (SCRIPT_READY)
  → enqueue generate_audio_task
  → enqueue generate_video_task (or fallback render)
```

### 3.3 Rendering Flow
```
Worker: render_reel_task
  → fetch image from S3
  → fetch audio from S3 (if TTS complete)
  → FFmpeg: compose 9:16 MP4 with subtitles + audio
  → upload MP4 + thumbnail to S3
  → update ReelVersion (READY_FOR_REVIEW)
  → notify via WebSocket or polling
```

---

## 4. Worker / Job Flow

```mermaid
stateDiagram-v2
    [*] --> DRAFT: user creates project
    DRAFT --> SCRIPT_GENERATING: generation started
    SCRIPT_GENERATING --> SCRIPT_READY: AI plan complete
    SCRIPT_GENERATING --> FAILED_SCRIPT: AI error
    SCRIPT_READY --> VIDEO_GENERATING: video task enqueued
    SCRIPT_READY --> AUDIO_GENERATING: TTS task enqueued
    VIDEO_GENERATING --> RENDERING: video + audio ready
    VIDEO_GENERATING --> FAILED_VIDEO: video error
    AUDIO_GENERATING --> RENDERING: (parallel merge)
    AUDIO_GENERATING --> FAILED_AUDIO: TTS error
    RENDERING --> READY_FOR_REVIEW: render complete
    RENDERING --> FAILED_RENDER: ffmpeg error
    READY_FOR_REVIEW --> APPROVED: user approves
    READY_FOR_REVIEW --> DRAFT: user rejects
    APPROVED --> PUBLISHING: publish triggered
    PUBLISHING --> IG_PROCESSING: container created
    IG_PROCESSING --> PUBLISHED: IG published
    IG_PROCESSING --> FAILED_INSTAGRAM_PUBLISH: IG error
    PUBLISHING --> FAILED_INSTAGRAM_UPLOAD: upload error
```

---

## 5. Storage Flow

```
User Image Upload:
  Browser → API (get pre-signed URL) → Browser → S3 (direct upload)

Asset Storage:
  Worker → S3 (store audio, video, thumbnail)
  S3 path pattern: {workspace_id}/{project_id}/{version_id}/{asset_type}.{ext}

Instagram Publish:
  Worker → Instagram API (provide S3 public URL for media container)
  Instagram → pulls media from S3 URL
  S3 bucket must allow public read for IG-accessible objects (scoped TTL)
```

---

## 6. Instagram Publishing Flow

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant W as Worker
    participant IG as Instagram Graph API
    participant DB as PostgreSQL

    U->>API: POST /publish-jobs
    API->>DB: create PublishJob (QUEUED)
    API->>W: enqueue publish_reel_task
    W->>IG: POST /media (create container with video URL)
    IG-->>W: container_id
    W->>DB: update PublishJob (CONTAINER_CREATED)
    loop Poll until FINISHED or ERROR
        W->>IG: GET /{container_id}?fields=status_code
        IG-->>W: status_code
    end
    W->>IG: POST /media_publish (container_id)
    IG-->>W: media_id
    W->>DB: update PublishJob (PUBLISHED) + store media_id
    W->>DB: write AuditLog entry
```

---

## 7. Security Boundaries

```
Internet ──► Nginx/LB ──► Frontend (Next.js, no direct DB access)
                      ──► API (FastAPI, JWT-validated routes)
                               │
                               ├── DB: internal network only
                               ├── Redis: internal network only
                               └── S3: IAM role / env-based credentials

Worker: internal only, never exposed to internet
Meta OAuth: handled via API callback, tokens encrypted at rest
Secrets: environment variables only, never in code or logs
```

---

## 8. Architectural Decisions

See [`docs/DECISIONS/`](./DECISIONS/) for all Architecture Decision Records (ADRs):

- [ADR-0001: Tech Stack Selection](./DECISIONS/ADR-0001-tech-stack.md)
- [ADR-0002: Instagram API Strategy](./DECISIONS/ADR-0002-instagram-api.md)
- [ADR-0003: Video Provider Abstraction](./DECISIONS/ADR-0003-video-provider-abstraction.md)
