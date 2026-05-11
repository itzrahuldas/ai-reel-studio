# Production Launch Checklist

Use this checklist before launching AI Reel Studio beyond staging. Keep every
secret in the production secret manager or deployment platform; do not paste
secrets into docs, tickets, chat, or screenshots.

## Infrastructure

- [ ] Production web service is provisioned.
- [ ] Production API service is provisioned.
- [ ] Dedicated workers are provisioned:
      - `worker-generation`
      - `worker-rendering`
      - `worker-publishing`
- [ ] `celery-beat` is provisioned as a singleton process.
- [ ] PostgreSQL production database is provisioned.
- [ ] Redis production instance is provisioned.
- [ ] Public object/media storage is provisioned.
- [ ] Network access allows API and workers to reach Postgres, Redis, storage,
      Stripe, Meta Graph API, and OpenAI.
- [ ] Runtime resources are sized for expected generation/render load.

## Environment Variables

- [ ] Production values are prepared from
      `docs/PRODUCTION_ENV_TEMPLATE_NOTES.md`.
- [ ] `APP_ENV=production`.
- [ ] `DEBUG=false`.
- [ ] `SECRET_KEY` is strong and unique to production.
- [ ] `TOKEN_ENCRYPTION_KEY` is strong, backed up securely, and never rotated
      without a token migration plan.
- [ ] `FRONTEND_URL` and `API_PUBLIC_BASE_URL` use production HTTPS domains.
- [ ] `ALLOWED_ORIGINS` includes only trusted production origins.
- [ ] No staging, localhost, or mock secrets are used in production.

## Database Migrations

- [ ] Production database backup exists before migration.
- [ ] Alembic migration command is documented for the production environment.
- [ ] Migration dry run or staging migration has passed.
- [ ] Migrations are applied before new workers start processing jobs.
- [ ] Migration result is verified.
- [ ] Rollback plan covers both app version and database changes.

## Object And Media Storage

- [ ] Production storage bucket/container exists.
- [ ] Rendered MP4 assets are accessible through public HTTPS URLs when needed
      for Instagram publishing.
- [ ] Upload limits match application expectations.
- [ ] Storage lifecycle/retention policy is defined.
- [ ] Bucket permissions prevent public listing.
- [ ] Write credentials are scoped to the app.
- [ ] CDN or signed/public URL behavior is tested.

## Redis And Celery Workers

- [ ] `CELERY_BROKER_URL` points to production Redis.
- [ ] `CELERY_RESULT_BACKEND` points to production Redis or approved result
      backend.
- [ ] Generation worker consumes the generation queue.
- [ ] Rendering worker consumes the rendering queue.
- [ ] Publishing worker consumes the publishing queue.
- [ ] Worker logs are visible and do not expose secrets.
- [ ] Failed job retry behavior is understood.
- [ ] Redis memory, eviction, and persistence policies are appropriate.

## Celery Beat

- [ ] Exactly one `celery-beat` instance is running.
- [ ] Scheduled publish polling/dispatch is enabled.
- [ ] Beat schedule survives restarts or is intentionally rebuilt at startup.
- [ ] Beat logs are monitored.

## Web And API Healthchecks

- [ ] Web healthcheck probes `http://127.0.0.1:3000/` inside the container.
- [ ] API health endpoint returns healthy.
- [ ] Postgres healthcheck passes.
- [ ] Redis healthcheck passes.
- [ ] Production load balancer uses health endpoints.
- [ ] Failed healthchecks trigger restart or alerting.

## Stripe Live Mode

- [ ] `STRIPE_MODE=live`.
- [ ] Live Stripe secret key is configured.
- [ ] Live webhook secret is configured.
- [ ] Live price IDs are configured.
- [ ] Webhook endpoint is public HTTPS.
- [ ] Stripe webhook delivery succeeds.
- [ ] Checkout success/cancel URLs use production domains.
- [ ] Customer Portal return URL uses production domain.
- [ ] Test purchase uses Stripe test/live mode appropriate to launch plan.

## Meta Live Mode

- [ ] `INSTAGRAM_INTEGRATION_MODE=live`.
- [ ] Meta app ID and secret are production-ready.
- [ ] Meta OAuth redirect URI uses production HTTPS API domain.
- [ ] App Review approval is granted for:
      - `instagram_basic`
      - `instagram_content_publish`
      - `pages_show_list`
- [ ] `pages_read_engagement` is not requested.
- [ ] Test Facebook Page is linked to an Instagram Business or Creator account.
- [ ] OAuth callback succeeds in production.
- [ ] Rendered media public URL is reachable by Meta.
- [ ] Publish job reaches published or a clear recoverable failure state.

## OpenAI Live Mode

- [ ] `AI_PROVIDER=openai` if live AI generation is enabled.
- [ ] `AI_API_KEY` is configured in the secret manager.
- [ ] Image analysis provider/model are configured.
- [ ] TTS provider/model/voice are configured.
- [ ] Cost limits and usage monitoring are configured.
- [ ] Mock provider is disabled for production user flows.

## Domain, HTTPS, And CORS

- [ ] Production app domain is configured.
- [ ] Production API domain is configured.
- [ ] TLS certificates are active and auto-renewing.
- [ ] HTTP redirects to HTTPS.
- [ ] CORS allows only production frontend origins.
- [ ] Cookie/token behavior is checked across production domains.
- [ ] Meta, Stripe, and privacy/deletion URLs use production HTTPS.

## Monitoring And Logging

- [ ] API logs are collected.
- [ ] Worker logs are collected.
- [ ] Web logs are collected.
- [ ] Error monitoring is configured.
- [ ] Healthcheck alerts are configured.
- [ ] Queue depth alerts are configured.
- [ ] Render failure and publish failure alerts are configured.
- [ ] Logs redact access tokens, app secrets, API keys, and passwords.

## Backups

- [ ] Automated Postgres backups are enabled.
- [ ] Backup restore has been tested.
- [ ] Object storage retention/versioning policy is documented.
- [ ] Secret backup/recovery process is documented.
- [ ] Database backup schedule and retention are approved.

## Security

- [ ] Secrets are stored only in approved secret storage.
- [ ] Production database is not publicly exposed.
- [ ] Redis is not publicly exposed.
- [ ] Admin/debug endpoints are disabled or protected.
- [ ] `DEBUG=false`.
- [ ] Token encryption key is protected.
- [ ] OAuth tokens are encrypted at rest.
- [ ] Access logs do not include sensitive query strings.
- [ ] Dependency vulnerability review is complete or accepted for launch.

## Rate Limits And Quotas

- [ ] App-level generation limits are configured.
- [ ] Render limits are configured.
- [ ] Publish limits are configured.
- [ ] Scheduled publish limits are configured.
- [ ] API rate limiting is enabled.
- [ ] Stripe, Meta, OpenAI, and storage quotas are known.
- [ ] Abuse handling process is documented.

## Rollback Plan

- [ ] Previous production image/tag is known.
- [ ] Rollback command is documented for web, API, workers, and beat.
- [ ] Database migration rollback strategy is documented.
- [ ] Queue-drain or pause steps are documented.
- [ ] Support/customer communication plan exists.
- [ ] Rollback owner and decision point are assigned.

## Smoke Tests

- [ ] Register/login works.
- [ ] Dashboard loads.
- [ ] API health is healthy.
- [ ] Create Reel works.
- [ ] Render MP4 works.
- [ ] Stripe Checkout or billing mock/live path matches launch plan.
- [ ] Meta OAuth callback works.
- [ ] Instagram account card appears.
- [ ] Publish or schedule path works with a non-sensitive test Reel.
- [ ] Logs remain secret-safe during the smoke test.

## Launch-Day Checklist

- [ ] Freeze non-launch changes.
- [ ] Confirm current git commit/tag.
- [ ] Confirm production env values are loaded.
- [ ] Deploy web/API/workers/beat.
- [ ] Apply migrations.
- [ ] Run smoke tests.
- [ ] Watch logs and queue depth.
- [ ] Verify payments, OAuth, rendering, and publishing.
- [ ] Announce launch only after smoke checks pass.

## Post-Launch Checklist

- [ ] Monitor errors for the first 24 hours.
- [ ] Monitor OpenAI/Stripe/Meta API errors.
- [ ] Monitor queue backlog.
- [ ] Review first user generation/render/publish failures.
- [ ] Confirm backup job completed after launch.
- [ ] Capture launch notes and follow-up issues.
- [ ] Schedule a post-launch security/logging review.
