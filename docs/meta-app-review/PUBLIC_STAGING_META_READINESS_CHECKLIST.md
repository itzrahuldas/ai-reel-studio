# Public Staging Meta Readiness Checklist

Use this checklist after public HTTPS staging is deployed and before filling the
final Meta App Review placeholders.

## Public Staging

- [ ] Public HTTPS frontend works:
      `https://app-staging.<your-domain>`.
- [ ] Public HTTPS API works:
      `https://api-staging.<your-domain>/health`.
- [ ] API readiness works:
      `https://api-staging.<your-domain>/api/v1/health/readiness`.
- [ ] Privacy page is public over HTTPS.
- [ ] Data deletion instructions are public over HTTPS.
- [ ] Static/media URL is public over HTTPS:
      `https://api-staging.<your-domain>/static` or configured S3-compatible
      public storage.

## OAuth Configuration

- [ ] `META_REDIRECT_URI` exactly matches:
      `https://api-staging.<your-domain>/api/v1/integrations/instagram/callback`.
- [ ] Meta Dashboard Valid OAuth Redirect URI matches `META_REDIRECT_URI`
      exactly.
- [ ] Meta Dashboard app/site URL uses `https://app-staging.<your-domain>`.
- [ ] Meta Dashboard does not include localhost redirect URIs for the review
      staging app.
- [ ] `INSTAGRAM_INTEGRATION_MODE=live`.
- [ ] Staging uses the same `META_APP_ID` configured in the Meta Dashboard.

## Permissions

- [ ] OAuth prompt shows only:
      `instagram_basic`, `instagram_content_publish`, `pages_show_list`.
- [ ] `pages_read_engagement` is not requested.
- [ ] No comments, messages, ads, business management, or unrelated Page
      permissions are requested.

## Test User And Instagram Account

- [ ] Facebook test user has access to the Facebook Page.
- [ ] Facebook Page is linked to an Instagram Business or Creator account.
- [ ] Instagram account is not a personal account.
- [ ] Test user can select/grant the Page during OAuth.
- [ ] Connected Instagram account appears in AI Reel Studio after OAuth.

## Publish Flow

- [ ] Staging account can create a reel.
- [ ] Rendering completes and produces a public HTTPS media URL.
- [ ] Meta can fetch the rendered media URL.
- [ ] Publish now flow was tested successfully.
- [ ] Scheduled publish flow was tested if it appears in the screencast.
- [ ] Publish History shows the test publish result.

## Submission Evidence

- [ ] Reviewer AI Reel Studio login credentials are staged and documented in the
      reviewer template.
- [ ] Screencast shows the public staging app URL.
- [ ] Screencast shows the OAuth prompt with only the requested permissions.
- [ ] Screencast shows connect, create, render, publish or schedule, and Publish
      History.
- [ ] Screencast does not show terminal windows, `.env` files, secrets, access
      tokens, database consoles, or real customer data.
