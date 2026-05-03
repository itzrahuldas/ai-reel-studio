# Instagram Integration — AI Reel Studio

**Version:** 0.1.0
**Last Updated:** 2026-05-03
**API Version:** Meta Graph API v21.0

---

## 1. OAuth Flow

### 1.1 Initiation
```
GET /api/v1/social-accounts/instagram/connect?workspace_id={id}

→ API builds Meta OAuth URL:
  https://www.facebook.com/v21.0/dialog/oauth?
    client_id={META_APP_ID}
    &redirect_uri={META_REDIRECT_URI}
    &scope=instagram_basic,instagram_content_publish,pages_read_engagement
    &response_type=code
    &state={signed_csrf_token}

→ Return { auth_url } to frontend
→ Frontend redirects user to auth_url
```

### 1.2 Callback
```
GET /api/v1/social-accounts/instagram/callback?code={code}&state={state}

→ Validate CSRF state token
→ Exchange code for access token:
  POST https://graph.facebook.com/v21.0/oauth/access_token
    client_id, client_secret, code, redirect_uri
→ Receive short-lived token
→ Exchange for long-lived token (60 days):
  GET /oauth/access_token?grant_type=fb_exchange_token&...
→ Fetch connected IG Business Account:
  GET /me/accounts → find page → GET /{page_id}?fields=instagram_business_account
→ Store: access_token_encrypted, platform_user_id, platform_username, page_id
→ Create or update SocialAccount record
→ Redirect to /dashboard/integrations
```

---

## 2. Connected Account Model

```python
class SocialAccount:
    platform: str              # "instagram"
    platform_user_id: str      # Instagram Business Account ID
    platform_username: str     # @handle
    platform_page_id: str      # Facebook Page ID
    access_token_encrypted: str # AES-256 encrypted token
    token_expires_at: datetime  # 60 days from connection
    status: str                # connected | reconnect_required | error
    scopes: list[str]          # ['instagram_basic', 'instagram_content_publish', ...]
```

---

## 3. Token Storage Strategy

- Tokens stored **encrypted** using `TOKEN_ENCRYPTION_KEY` (AES-256-GCM)
- Encryption handled in `app/utils/encryption.py`
- Token is decrypted only in memory at time of API call
- Token is **never logged** — logging helpers strip it automatically
- `token_expires_at` checked before every publish attempt
- If `token_expires_at - now() < 7 days`: proactive reconnect prompt shown

---

## 4. Publishing Workflow

### 4.1 Required Conditions
- `ReelProject.status == APPROVED`
- `SocialAccount.status == connected`
- `SocialAccount.token_expires_at > now()`
- `ReelVersion.rendered_asset_id` is set
- Rendered video accessible via public S3 URL (temporary signed URL or public bucket)

### 4.2 Step-by-Step
```
1. create_media_container(ig_user_id, video_url, caption)
   POST /v21.0/{ig_user_id}/media
     media_type=REELS
     video_url={public_s3_signed_url}
     caption={caption + hashtags}
     share_to_feed=true
   → receive: container_id

2. poll_container_status(container_id)
   GET /v21.0/{container_id}?fields=status_code
   → status_code: IN_PROGRESS | FINISHED | ERROR | EXPIRED

3. If FINISHED → publish
   POST /v21.0/{ig_user_id}/media_publish
     creation_id={container_id}
   → receive: media_id (published IG post ID)

4. Store ig_media_id in PublishJob
5. Update ReelProject.status = PUBLISHED
6. Write AuditLog entry
```

---

## 5. Polling Strategy

```python
MAX_POLLS = 20
POLL_INTERVAL_SECONDS = 10  # 20 × 10s = ~3.3 minutes max wait

def poll_instagram_status_task(publish_job_id: str, attempt: int = 0):
    job = load_publish_job(publish_job_id)
    status = ig_client.check_container_status(job.ig_container_id)
    
    if status == "FINISHED":
        publish_and_complete(job)
    elif status == "ERROR":
        mark_failed(job, "Instagram container processing failed")
    elif attempt >= MAX_POLLS:
        mark_failed(job, "Instagram container polling timeout")
    else:
        # Re-enqueue with countdown
        poll_instagram_status_task.apply_async(
            args=[publish_job_id, attempt + 1],
            countdown=POLL_INTERVAL_SECONDS
        )
```

---

## 6. Reconnect Strategy

**Trigger conditions:**
- OAuth error code 190 (token invalid/expired)
- `token_expires_at < now()`
- API response: `{"error": {"code": 190, ...}}`

**Flow:**
```
1. Worker catches OAuthException(code=190)
2. Update SocialAccount.status = "reconnect_required"
3. Update PublishJob.status = "failed", error = "TOKEN_EXPIRED"
4. Write AuditLog entry
5. Frontend: /dashboard/integrations shows reconnect banner
6. User clicks "Reconnect Instagram"
7. OAuth flow re-initiates (same as initial connection)
8. New token stored, SocialAccount.status = "connected"
9. User can retry publish
```

---

## 7. Meta App Review Checklist

Before submitting for Meta App Review, verify:

- [ ] App is registered in Meta for Developers (developers.facebook.com)
- [ ] App type: **Business** (required for Reels publishing)
- [ ] Required permissions requested:
  - `instagram_basic`
  - `instagram_content_publish`
  - `pages_read_engagement`
- [ ] Redirect URI registered in app settings
- [ ] Privacy Policy URL configured in app settings
- [ ] Terms of Service URL configured
- [ ] Data Use Checkup completed
- [ ] Video walkthrough of publishing flow recorded for review submission
- [ ] Test with test users before App Review submission
- [ ] Rate limits documented and respected:
  - 25 API calls per user per day (content publishing limit)
  - 200 calls per user per hour (general rate limit)
- [ ] App Review submission typically takes 2–6 weeks

---

## 8. Risks and Limitations

| Risk                            | Mitigation                                              |
|---------------------------------|---------------------------------------------------------|
| App Review rejection            | Test thoroughly, follow Meta policies, prepare appeal   |
| Token expiry (60-day limit)     | Proactive reconnect prompts + monitoring                |
| 25 posts/day limit per account  | Display limit status in dashboard, prevent over-posting |
| Video format requirements       | Validate before upload: MP4, H.264, AAC audio, 9:16    |
| IG container processing failure | Retry up to 3 times, fallback error UI                  |
| Scope changes from Meta         | Monitor Meta changelog, test quarterly                  |
| Business verification required  | Document requirement for users with business accounts   |

---

## 9. Video Requirements (Instagram Reels via API)

| Property     | Requirement                    |
|--------------|--------------------------------|
| Format       | MP4 (H.264 video, AAC audio)  |
| Aspect Ratio | 9:16 (vertical)                |
| Min Res      | 500 x 888 px                   |
| Max Res      | 1080 x 1920 px (recommended)   |
| Duration     | 3–90 seconds                   |
| Max File Size| 1 GB                           |
| Frame Rate   | 23–60 FPS                      |

See [`docs/VIDEO_RENDERING.md`](./VIDEO_RENDERING.md) for rendering specs.
