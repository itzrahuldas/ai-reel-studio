# Public Staging Deployment Runbook

Use this runbook to deploy AI Reel Studio to a public HTTPS staging VM before
Meta App Review. The target shape is:

- Frontend: `https://app-staging.<your-domain>`
- API: `https://api-staging.<your-domain>`
- Meta OAuth callback:
  `https://api-staging.<your-domain>/api/v1/integrations/instagram/callback`
- Local media/static base: `https://api-staging.<your-domain>/static`

Do not commit `.env.public-staging`, real Meta credentials, database passwords,
tokens, API keys, private keys, or screenshots that reveal secrets.

## 1. Provision The Server

1. Create a VPS/cloud VM with enough disk for Docker images, Postgres data, Redis
   data, Caddy certificates, and staging media.
2. Open inbound TCP `80` and `443`.
3. Keep Postgres and Redis private to the Docker network; do not open `5432` or
   `6379` to the internet.
4. Install Docker Engine and the Docker Compose plugin from the official Docker
   packages for your VM OS.
5. Confirm Compose is available:

   ```bash
   docker compose version
   ```

## 2. Point DNS

Create DNS `A` records pointing at the server public IP:

| Hostname | Target |
| --- | --- |
| `app-staging.<your-domain>` | `<server-public-ip>` |
| `api-staging.<your-domain>` | `<server-public-ip>` |

Wait for DNS to resolve from outside the server before starting Caddy:

```bash
dig +short app-staging.<your-domain>
dig +short api-staging.<your-domain>
```

## 3. Copy The Repository

Clone the staging branch on the server, or copy the repository by your normal
release process:

```bash
git clone <repo-url> ai-reel-studio
cd ai-reel-studio
git checkout chore/staging-deployment-setup
```

Replace the placeholders in `deploy/Caddyfile.public-staging` with the real
staging hostnames:

```caddyfile
app-staging.<your-domain> {
    reverse_proxy web:3000
}

api-staging.<your-domain> {
    reverse_proxy api:8000
}
```

## 4. Create The Public Staging Env File

Copy the template and edit only on the server:

```bash
cp .env.public-staging.example .env.public-staging
chmod 600 .env.public-staging
```

Fill every `<...>` placeholder in `.env.public-staging`. Keep:

```bash
APP_ENV=staging
DEBUG=false
FRONTEND_URL=https://app-staging.<your-domain>
API_PUBLIC_BASE_URL=https://api-staging.<your-domain>
NEXT_PUBLIC_API_URL=https://api-staging.<your-domain>
ALLOWED_ORIGINS=["https://app-staging.<your-domain>"]
STORAGE_PROVIDER=local
STORAGE_PUBLIC_BASE_URL=https://api-staging.<your-domain>/static
META_REDIRECT_URI=https://api-staging.<your-domain>/api/v1/integrations/instagram/callback
INSTAGRAM_INTEGRATION_MODE=live
STRIPE_MODE=mock
AI_PROVIDER=mock
IMAGE_ANALYSIS_PROVIDER=mock
TTS_PROVIDER=mock
```

Generate `SECRET_KEY` and `TOKEN_ENCRYPTION_KEY` on the server and paste them
directly into `.env.public-staging`. Do not share the command output:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

Configure these server-only secrets and identifiers:

- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL`
- `SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`
- `META_APP_ID`, `META_APP_SECRET`
- S3-compatible storage credentials only if switching `STORAGE_PROVIDER=s3`
- Optional provider keys only if intentionally testing live Stripe or AI

## 5. Validate Compose Configuration

Run this before starting containers:

```bash
docker compose \
  -f docker-compose.staging.yml \
  -f docker-compose.public-staging.yml \
  --env-file .env.public-staging \
  config
```

If Compose reports an unknown `!reset` tag, upgrade the Docker Compose plugin.

## 6. Start Public Staging

Build and start the stack:

```bash
docker compose \
  -f docker-compose.staging.yml \
  -f docker-compose.public-staging.yml \
  --env-file .env.public-staging \
  up -d --build
```

Run migrations:

```bash
docker compose \
  -f docker-compose.staging.yml \
  -f docker-compose.public-staging.yml \
  --env-file .env.public-staging \
  run --rm api alembic upgrade head
```

If this is the first boot and the API was unhealthy before migrations, repeat
the `up -d` command after migrations complete.

## 7. Verify HTTPS And Health

From a machine outside the VM:

```bash
curl https://app-staging.<your-domain>
curl https://api-staging.<your-domain>/health
curl https://api-staging.<your-domain>/api/v1/health/readiness
```

On the server, confirm only Caddy publishes public ports and Postgres/Redis are
not exposed:

```bash
docker compose \
  -f docker-compose.staging.yml \
  -f docker-compose.public-staging.yml \
  --env-file .env.public-staging \
  ps
```

## 8. Run Smoke Tests

Run the smoke test from a trusted machine with a staging-only account:

```bash
SMOKE_API_BASE_URL=https://api-staging.<your-domain> \
SMOKE_FRONTEND_BASE_URL=https://app-staging.<your-domain> \
SMOKE_TEST_EMAIL=<staging-smoke-email> \
SMOKE_TEST_PASSWORD='<staging-smoke-password>' \
SMOKE_CREATE_REEL=true \
SMOKE_TEST_STRIPE_MOCK=false \
SMOKE_TEST_INSTAGRAM_MOCK=false \
python scripts/staging_smoke_test.py
```

Use the UI and worker logs to verify reel generation/rendering. For Meta review,
test the real OAuth connect and publish flow manually with the Meta test user.

## 9. Configure Meta Dashboard

In the Meta app dashboard:

1. Add `https://api-staging.<your-domain>/api/v1/integrations/instagram/callback`
   as the Valid OAuth Redirect URI.
2. Set the staging app/site URL to `https://app-staging.<your-domain>`.
3. Confirm the app ID and app secret match `.env.public-staging`.
4. Confirm the OAuth prompt requests only:
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`.

## 10. Test OAuth Connect

1. Log in to `https://app-staging.<your-domain>` with the reviewer/staging
   account.
2. Open Integrations and click Instagram Connect.
3. Complete OAuth with the Facebook test user.
4. Confirm the selected Facebook Page is linked to an Instagram Business or
   Creator account.
5. Confirm the connected account card appears.
6. Render a non-sensitive test reel and publish or schedule it through the
   official Meta Graph API flow.

## 11. Operational Notes

- Caddy stores certificates in the `caddy_data` Docker volume.
- Postgres data stays in `staging_postgres_data`.
- Redis data stays in `staging_redis_data`.
- Local media stays in `staging_media`; switch to S3-compatible public storage
  before higher-risk or longer-lived staging usage.
- Do not run destructive volume removal commands against staging.
