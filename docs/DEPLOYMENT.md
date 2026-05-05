# Deployment Guide — AI Reel Studio

**Version:** 0.1.0
**Last Updated:** 2026-05-03

---

## 1. Local Development

### Prerequisites
- Docker Desktop v4.x+
- Node.js 20+
- Python 3.12+
- Git

### Steps
```bash
git clone https://github.com/your-org/ai-reel-studio.git
cd ai-reel-studio
cp .env.example .env
# Fill in .env values

# Start all services
docker compose up --build

# Or run individually:
# Frontend
cd apps/web && npm install && npm run dev

# Backend
cd apps/api && pip install -e ".[dev]" && uvicorn app.main:app --reload

# Worker
cd apps/worker && celery -A app.main worker --loglevel=info --pool=solo
```

---

## 2. Staging Deployment

### Docker Compose on VPS/VM
```bash
# On server
git clone https://github.com/your-org/ai-reel-studio.git
cd ai-reel-studio
cp .env.example .env.staging
# Fill in staging values

docker compose -f docker-compose.yml --env-file .env.staging up -d --build

# Run migrations
docker compose exec api alembic upgrade head
```

### Environment Variables for Staging
- `APP_ENV=staging`
- `API_BASE_URL=https://api.staging.yourapp.com`
- `FRONTEND_URL=https://staging.yourapp.com`
- Use staging credentials for Meta app (test users only)

---

## 3. Production Deployment

### Recommended Stack
- **Frontend**: Vercel or Cloudflare Pages
- **API + Worker**: Railway, Render, or AWS ECS/Fargate
- **Database**: AWS RDS PostgreSQL / Supabase / Neon
- **Redis**: AWS ElastiCache / Upstash
- **Storage**: AWS S3 (primary)
- **CDN**: CloudFront for S3 assets

### Deployment Checklist
- [ ] All env variables set in production secrets manager
- [ ] `APP_ENV=production` set
- [ ] `SECRET_KEY` is a cryptographically random 64-char string
- [ ] `TOKEN_ENCRYPTION_KEY` is a 64-char hex string (32 random bytes)
- [ ] Database SSL connection enabled (`?sslmode=require` in DATABASE_URL)
- [ ] Redis password set
- [ ] CORS restricted to production frontend URL only
- [ ] Rate limiting Redis backend configured
- [ ] Alembic migrations run before deploying new API version
- [ ] Meta App in Live mode (not Development mode)
- [ ] Stripe mode is `live`, recurring Price IDs are set, and webhook endpoint is registered
- [ ] S3 bucket policy configured for IG media access (temporary signed URLs)
- [ ] Monitoring configured (see below)

---

## 4. Environment Variables

See [`.env.example`](../.env.example) for the full list.

| Variable               | Required | Description                          |
|------------------------|----------|--------------------------------------|
| DATABASE_URL           | ✅       | PostgreSQL connection string         |
| REDIS_URL              | ✅       | Redis connection string              |
| SECRET_KEY             | ✅       | JWT signing key (64 chars random)    |
| TOKEN_ENCRYPTION_KEY   | ✅       | AES-256 key for token encryption     |
| META_APP_ID            | ✅       | Meta for Developers App ID           |
| META_APP_SECRET        | ✅       | Meta App Secret                      |
| META_REDIRECT_URI      | ✅       | OAuth callback URL                   |
| AI_PROVIDER            | ✅       | openai / gemini / anthropic          |
| AI_API_KEY             | ✅       | LLM provider API key                 |
| VIDEO_PROVIDER         | ❌       | runway / luma / stability / none     |
| TTS_PROVIDER           | ✅       | elevenlabs / openai / google         |
| STORAGE_PROVIDER       | ✅       | s3 / local                           |
| S3_BUCKET              | ✅*      | S3 bucket name (*if s3 provider)     |
| S3_ACCESS_KEY_ID       | ✅*      | S3 access key                        |
| S3_SECRET_ACCESS_KEY   | ✅*      | S3 secret key                        |
| S3_ENDPOINT_URL        | ❌       | Custom S3 endpoint (MinIO, etc.)     |
| STRIPE_MODE            | ✅       | `mock` for local dev, `live` for production |
| STRIPE_SECRET_KEY      | ✅*      | Stripe secret key (*live mode)       |
| STRIPE_WEBHOOK_SECRET  | ✅*      | Stripe webhook signing secret (*live mode) |
| STRIPE_CREATOR_PRICE_ID| ✅*      | Creator recurring price ID (*live mode) |
| STRIPE_PRO_PRICE_ID    | ✅*      | Pro recurring price ID (*live mode)  |
| STRIPE_CUSTOMER_PORTAL_RETURN_URL | ❌ | Customer Portal return URL override |
| STRIPE_CHECKOUT_SUCCESS_URL | ❌   | Checkout success URL override        |
| STRIPE_CHECKOUT_CANCEL_URL | ❌    | Checkout cancel URL override         |
| STRIPE_API_VERSION     | ❌       | Optional pinned Stripe API version   |

---

## 5. Worker Deployment

```bash
# Production worker command
celery -A app.main worker \
  --loglevel=info \
  --concurrency=4 \
  --queues=default,generation,rendering,publishing \
  --max-tasks-per-child=100

# Celery Beat (scheduler)
celery -A app.main beat --loglevel=info
```

- Scale workers horizontally per queue type
- `rendering` queue: needs FFmpeg installed in worker image
- `publishing` queue: needs network access to Meta API

---

## 6. Storage Setup

### AWS S3
```bash
aws s3 mb s3://ai-reel-studio-prod
aws s3api put-bucket-versioning \
  --bucket ai-reel-studio-prod \
  --versioning-configuration Status=Enabled
# Set lifecycle policy for 30-day media expiry
```

### MinIO (Local Dev)
```bash
# MinIO included in docker-compose.yml
# Access: http://localhost:9001
# Default credentials from .env
```

---

## 7. Database Migration Setup

```bash
# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "add_scheduled_publish"

# Rollback one step
alembic downgrade -1

# Check current version
alembic current
```

---

## 8. Monitoring

### Recommended Stack
- **Logs**: Structured JSON logs → Loki / CloudWatch Logs
- **Metrics**: Prometheus + Grafana (or Datadog)
- **Errors**: Sentry (add `SENTRY_DSN` to env)
- **Uptime**: Better Uptime / Pingdom

### Key Metrics to Monitor
- API response time P50/P95/P99
- Celery queue depth per queue
- Failed task rate by task type
- Instagram publish success rate
- Generation job duration P50/P95
- S3 storage costs
- Database connection pool utilization
