# Skill: Instagram Publishing

## OAuth Rules
- Always generate a CSRF state token (signed JWT, 10-min expiry)
- Validate state token on callback before any token exchange
- Use esponse_type=code (authorization code flow, not implicit)
- Redirect URI must exactly match the registered URI in Meta app settings
- Minimum required scopes: instagram_basic,instagram_content_publish,pages_read_engagement

## Token Safety
- NEVER log access tokens — use '[REDACTED]' placeholder
- NEVER return access tokens in API responses
- Store tokens encrypted (AES-256-GCM) using TOKEN_ENCRYPTION_KEY
- Decrypt only in memory at time of API call
- Check expiry before every publish attempt
- Refresh token at least 7 days before expiry if possible

## Media Container Flow
1. Validate all preconditions (status, token, video format)
2. Get signed S3 URL for rendered video (temporary, 24hr expiry)
3. POST to /{ig_user_id}/media with media_type=REELS
4. Store container_id in PublishJob immediately
5. Never assume container creation = success

## Publish Polling
- Poll every 10 seconds
- Max 20 polls (3.3 minutes total)
- status_code values: IN_PROGRESS | FINISHED | ERROR | EXPIRED
- On FINISHED: call /{ig_user_id}/media_publish
- On ERROR or timeout: mark job FAILED, write AuditLog
- Always use Celery countdown (not sleep) for polling

## Reconnect Flow
- Detect token expiry: OAuthException code 190
- Update SocialAccount.status = 'reconnect_required'
- Write AuditLog with reason
- Never auto-reconnect without user action
- Frontend shows reconnect banner on /dashboard/integrations

## Audit Log Requirements
Every publish attempt MUST log:
- publish_job_id
- social_account_id (NOT the token)
- ig_user_id
- action: 'publish.started' | 'publish.container_created' | 'publish.succeeded' | 'publish.failed'
- error details (if failed)
- timestamp
