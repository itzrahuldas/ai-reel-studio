# Production Environment Template Notes

This file documents production environment variable groups. It intentionally
uses placeholders only. Do not paste real secrets into this document.

## App Runtime

```env
APP_ENV=production
DEBUG=false
APP_VERSION=<release-version-or-git-sha>
```

## Database

```env
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:5432/<database>
```

Use a production database user with the minimum required privileges. Store the
full URL in the deployment platform secret manager.

## Redis And Celery

```env
REDIS_URL=redis://<redis-host>:6379/0
CELERY_BROKER_URL=redis://<redis-host>:6379/0
CELERY_RESULT_BACKEND=redis://<redis-host>:6379/1
GENERATION_MODE=async
RENDER_MODE=async
PUBLISH_MODE=async
```

Redis must not be publicly exposed.

## Security

```env
SECRET_KEY=<strong-production-jwt-secret>
TOKEN_ENCRYPTION_KEY=<strong-production-token-encryption-key>
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30
```

Back up `TOKEN_ENCRYPTION_KEY` securely. Losing it can make encrypted OAuth
tokens unrecoverable.

## Public URLs And CORS

```env
FRONTEND_URL=https://<production-app-domain>
API_PUBLIC_BASE_URL=https://<production-api-domain>
ALLOWED_ORIGINS=https://<production-app-domain>
```

Do not include localhost or staging domains in production CORS unless there is a
documented operational reason.

## Storage

```env
STORAGE_PROVIDER=s3
STORAGE_PUBLIC_BASE_URL=https://<production-media-domain-or-bucket-public-base>
LOCAL_STORAGE_PATH=/var/lib/ai-reel-studio/media
```

If using S3-compatible object storage:

```env
S3_ENDPOINT_URL=<s3-endpoint-url-or-empty-for-aws>
S3_BUCKET=<production-bucket-name>
S3_ACCESS_KEY_ID=<production-storage-access-key-id>
S3_SECRET_ACCESS_KEY=<production-storage-secret-access-key>
S3_REGION=<production-storage-region>
```

Rendered MP4 URLs used for Instagram publishing must be reachable by Meta over
public HTTPS.

## Stripe Live Mode

```env
STRIPE_MODE=live
STRIPE_SECRET_KEY=<stripe-live-secret-key>
STRIPE_WEBHOOK_SECRET=<stripe-live-webhook-secret>
STRIPE_CREATOR_PRICE_ID=<stripe-live-creator-price-id>
STRIPE_PRO_PRICE_ID=<stripe-live-pro-price-id>
STRIPE_CUSTOMER_PORTAL_RETURN_URL=https://<production-app-domain>/dashboard/billing
STRIPE_CHECKOUT_SUCCESS_URL=https://<production-app-domain>/dashboard/billing/success
STRIPE_CHECKOUT_CANCEL_URL=https://<production-app-domain>/dashboard/billing/cancel
STRIPE_API_VERSION=<stripe-api-version-or-empty-to-use-sdk-default>
```

Use live price IDs only when the business is ready to accept real payments.

## Meta And Instagram Live Mode

```env
INSTAGRAM_INTEGRATION_MODE=live
META_APP_ID=<meta-app-id>
META_APP_SECRET=<meta-app-secret>
META_REDIRECT_URI=https://<production-api-domain>/api/v1/integrations/instagram/callback
META_GRAPH_API_VERSION=v21.0
```

The approved Meta permission set should be:

- `instagram_basic`
- `instagram_content_publish`
- `pages_show_list`

Do not request `pages_read_engagement` unless a future reviewed feature uses it.

## AI Provider

```env
AI_PROVIDER=openai
AI_API_KEY=<openai-api-key>
AI_MODEL=<openai-text-model>
IMAGE_ANALYSIS_PROVIDER=openai
IMAGE_ANALYSIS_MODEL=<openai-vision-capable-model>
AI_REQUEST_TIMEOUT_SECONDS=60
AI_MAX_RETRIES=2
AI_GENERATION_TEMPERATURE=0.7
```

## TTS Settings

```env
TTS_PROVIDER=openai
TTS_MODEL=<tts-model>
TTS_VOICE=<tts-voice>
TTS_PROVIDER_API_KEY=<tts-provider-api-key-if-different-from-ai-api-key>
```

If TTS uses the same OpenAI key as the AI provider, store the key once according
to the deployment platform's secret management conventions.

## Video Provider

```env
VIDEO_PROVIDER=none
VIDEO_PROVIDER_API_KEY=<video-provider-api-key-if-enabled>
```

Leave `VIDEO_PROVIDER=none` unless a production video provider has been tested
and approved.

## Rate Limits

```env
RATE_LIMIT_GENERATION_PER_HOUR=<production-generation-limit>
RATE_LIMIT_PUBLISH_PER_DAY=<production-publish-limit>
MAX_UPLOAD_BYTES=20971520
```

## Logging

```env
LOG_LEVEL=INFO
LOG_FORMAT=json
```

Logs must redact access tokens, authorization headers, app secrets, API keys,
webhook secrets, database passwords, and encryption keys.

## Final Production Env Review

- [ ] No placeholder values remain.
- [ ] No staging domains remain.
- [ ] No localhost values remain.
- [ ] No mock modes remain for live user flows.
- [ ] Secrets are stored in secret manager, not committed files.
- [ ] Values were reviewed by the launch owner.
