# 🎬 AI Reel Studio

> **Production-grade AI-powered platform to generate, review, and publish Instagram Reels from a text prompt and a single image.**

[![CI](https://github.com/your-org/ai-reel-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/ai-reel-studio/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Docker Compose Ready](https://img.shields.io/badge/docker--compose-ready-blue)](./docker-compose.yml)

---

## 📖 Product Overview

AI Reel Studio is a full-stack SaaS platform that transforms a business idea into a complete Instagram Reel — including script, storyboard, voiceover, subtitles, video, caption, and hashtags — in minutes.

The user provides:
1. A **text prompt** or business description
2. One **uploaded image**
3. Optional **brand/tone/language/duration** settings

The system produces:
1. Short-form Instagram Reel concept & script
2. Scene-by-scene storyboard
3. Caption + hashtags
4. AI voiceover audio (TTS)
5. Subtitle lines
6. A 9:16 MP4 video (AI-generated or FFmpeg-rendered fallback)
7. A preview page for review
8. A manual approval flow
9. A publish/schedule flow via the official Meta/Instagram Graph API

---

## 🔄 Core Workflow

```
User submits prompt + image
       ↓
AI Pipeline: analyze image → plan scenes → generate script → caption/hashtags
       ↓
Worker: generate voiceover → generate video or FFmpeg fallback render
       ↓
Review Page: user approves or regenerates
       ↓
Publish Job: create IG media container → poll status → publish → store result
```

Usage limits are enforced on create/generate, regenerate, render, publish now, schedule creation, and scheduled publish execution. Retries use the job ID as the usage idempotency key so the same job is not double-charged.

Stripe subscription billing connects `CREATOR` and `PRO` plans to hosted Checkout,
webhook-driven subscription updates, and Stripe Customer Portal management.

---

## 🛠 Tech Stack

| Layer        | Technology                                            |
|--------------|-------------------------------------------------------|
| Frontend     | Next.js 15, React, TypeScript, Tailwind CSS, Zustand  |
| Backend      | FastAPI, Python 3.12, Pydantic v2, SQLAlchemy 2       |
| Database     | PostgreSQL 16                                         |
| Queue/Cache  | Celery + Redis                                        |
| AI           | Provider-abstracted (OpenAI/Gemini/Anthropic)         |
| Video        | FFmpeg renderer + AI video provider adapter           |
| TTS          | Provider-abstracted (ElevenLabs/OpenAI/Google TTS)    |
| Storage      | S3-compatible (MinIO for local dev)                   |
| Instagram    | Meta Graph API v21 — OAuth + Reels publishing         |
| DevOps       | Docker Compose, GitHub Actions, Ruff, ESLint          |

---

## 🚀 Local Setup

### Prerequisites
- Docker & Docker Compose v2
- Node.js 20+
- Python 3.12+
- `make` (optional but recommended)

### 1. Clone & Configure
```bash
git clone https://github.com/your-org/ai-reel-studio.git
cd ai-reel-studio
cp .env.example .env
# Edit .env with your real credentials
```

### 2. Start All Services
```bash
docker compose up --build
```

Or using the helper scripts:
```bash
bash scripts/setup.sh   # first-time setup
bash scripts/dev.sh     # start dev environment
```

### 3. Access
| Service    | URL                         |
|------------|-----------------------------|
| Frontend   | http://localhost:3000       |
| Backend    | http://localhost:8000       |
| API Docs   | http://localhost:8000/docs  |
| MinIO UI   | http://localhost:9001       |

---

## 🔐 Environment Variables

See [`.env.example`](./.env.example) for all required variables. Key groups:

| Group       | Variables                                              |
|-------------|--------------------------------------------------------|
| Database    | `DATABASE_URL`                                         |
| Cache       | `REDIS_URL`                                            |
| AI          | `AI_PROVIDER`, `AI_API_KEY`                            |
| Video       | `VIDEO_PROVIDER`, `VIDEO_PROVIDER_API_KEY`             |
| TTS         | `TTS_PROVIDER`, `TTS_PROVIDER_API_KEY`                 |
| Storage     | `STORAGE_PROVIDER`, `S3_*` variables                   |
| Instagram   | `META_APP_ID`, `META_APP_SECRET`, `META_REDIRECT_URI`  |
| Security    | `SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`                   |
| Billing     | `STRIPE_MODE`, `STRIPE_SECRET_KEY`, `STRIPE_*_PRICE_ID` |

---

## 💻 Development Commands

```bash
# Frontend
cd apps/web && npm run dev          # start Next.js dev server
cd apps/web && npm run lint         # run ESLint
cd apps/web && npm run typecheck    # run TypeScript check

# Backend
cd apps/api && ruff check .         # lint
cd apps/api && ruff format .        # format
cd apps/api && pytest               # run tests
cd apps/api && pytest tests/unit/test_usage_service.py tests/unit/test_usage_enforcement.py --no-cov

# Worker
cd apps/worker && celery -A app.main worker --loglevel=info

# Database migrations
cd apps/api && alembic upgrade head
cd apps/api && alembic revision --autogenerate -m "description"

# Docker helpers
docker compose up --build           # start everything
docker compose down -v              # tear down
docker compose logs -f api          # tail logs
```

---

## 🏗 Architecture Overview

```
┌─────────────┐     HTTP/REST      ┌──────────────┐
│  Next.js    │ ─────────────────► │   FastAPI    │
│  Frontend   │ ◄───────────────── │   Backend    │
└─────────────┘                    └──────┬───────┘
                                          │ Celery tasks
                                   ┌──────▼───────┐
                                   │   Worker     │
                                   │   (Celery)   │
                                   └──────┬───────┘
                        ┌─────────────────┼─────────────────┐
                        ▼                 ▼                 ▼
                  ┌──────────┐    ┌──────────────┐  ┌──────────────┐
                  │ AI APIs  │    │ FFmpeg/Video │  │  Instagram   │
                  │ (LLM/TTS)│    │   Renderer   │  │  Graph API   │
                  └──────────┘    └──────────────┘  └──────────────┘
                        │                 │                 │
                        └────────────────►│◄────────────────┘
                                   ┌──────▼───────┐
                                   │  S3/Storage  │
                                   │  PostgreSQL  │
                                   │   Redis      │
                                   └──────────────┘
```

See [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) for the full system diagram.

---

## 🔒 Safety & Compliance Notes

- **No Instagram password automation** — only official Meta Graph API OAuth
- **No browser scraping or unofficial bots**
- **Secrets managed via environment variables only** — never hardcoded
- **Token encryption at rest** using `TOKEN_ENCRYPTION_KEY`
- **Content moderation** step built into the AI pipeline
- **Upload validation** enforced on all file inputs
- **Audit logs** recorded for all publish attempts
- **Rate limiting** applied at the API gateway level

---

## 📊 Current Project Status

| Phase | Description                    | Status        |
|-------|--------------------------------|---------------|
| 1     | Project Bootstrap & Docs       | ✅ Complete    |
| 2     | Agent System                   | ✅ Complete    |
| 3     | Frontend Implementation        | ✅ Skeleton    |
| 4     | Backend Implementation         | ✅ Skeleton    |
| 5     | AI Pipeline                    | ✅ Skeleton    |
| 6     | Video Rendering                | ✅ Skeleton    |
| 7     | Instagram Integration          | ✅ Skeleton    |
| 8     | Worker Queue                   | ✅ Skeleton    |
| 9     | DevOps                         | ✅ Complete    |
| 10    | GitHub Workflow                | ✅ Complete    |
| 11    | Quality Gate / Bootstrap Report| ✅ Complete    |

> **Next step:** Add real AI provider credentials and run the full generation pipeline end-to-end.

---

## 📁 Repository Structure

```
ai-reel-studio/
├── .agents/          # AI agent personas & workflow definitions
├── apps/
│   ├── web/          # Next.js 15 frontend
│   ├── api/          # FastAPI backend
│   └── worker/       # Celery worker
├── packages/
│   ├── shared/       # Shared TypeScript types
│   ├── ui/           # Shared UI components
│   └── prompts/      # LLM prompt templates
├── services/         # Service-level documentation
├── docs/             # Architecture, specs, decisions
├── infra/            # Docker, Terraform, CI configs
├── scripts/          # Developer helper scripts
└── .github/          # GitHub Actions & templates
```

---

## 🤝 Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md).

## 🔐 Security

See [`SECURITY.md`](./SECURITY.md) for responsible disclosure.

## 📄 License

MIT — see [`LICENSE`](./LICENSE).
