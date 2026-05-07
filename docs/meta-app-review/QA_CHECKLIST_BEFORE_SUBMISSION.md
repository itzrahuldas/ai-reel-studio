# QA Checklist Before Submission

Complete this checklist before submitting AI Reel Studio to Meta App Review.

## Staging And App Configuration

- [ ] Staging frontend HTTPS URL works:
      `https://<staging-app-domain>`.
- [ ] Staging API HTTPS URL works:
      `https://<staging-api-domain>`.
- [ ] No localhost URLs are used in the Meta review submission.
- [ ] No mock mode is used for review.
- [ ] Meta app mode, app type, products, domain, icon, and app name are
      configured.
- [ ] OAuth redirect URI exactly matches the deployed callback URL.
- [ ] Business verification status checked, if applicable.
- [ ] Privacy policy URL is public and entered in Meta app settings.
- [ ] Data deletion URL or public deletion instructions are entered in Meta app
      settings.

## Permission Scope Alignment

- [ ] OAuth prompt requests only permissions documented in
      `PERMISSION_JUSTIFICATIONS.md`.
- [ ] `instagram_basic` is requested and demonstrated by connected-account
      metadata.
- [ ] `instagram_content_publish` is requested and demonstrated by the publish
      or schedule flow.
- [ ] `pages_show_list` is requested and demonstrated by Page-to-Instagram
      account resolution.
- [ ] `pages_read_engagement` is not requested unless staging proves it is
      required for Page metadata lookup.
- [ ] If `pages_read_engagement` is not required, it is removed from the OAuth
      scope list before final review.
- [ ] No unused permissions are requested:
      - `instagram_manage_comments`
      - `instagram_manage_messages`
      - `ads_management`
      - `business_management`
      - `pages_manage_posts`
      - `pages_manage_metadata`

## Reviewer Account And Meta Test Setup

- [ ] AI Reel Studio reviewer credentials work.
- [ ] Reviewer account has enough usage quota for create, render, publish, and
      schedule testing.
- [ ] Facebook test user can log in to Meta OAuth.
- [ ] Facebook test user has access to the test Facebook Page.
- [ ] Facebook Page is linked to an Instagram Business or Creator account.
- [ ] Personal Instagram accounts are not used for review.

## End-To-End Product Flow

- [ ] Login succeeds.
- [ ] `Dashboard` loads.
- [ ] `Integrations` page loads.
- [ ] Instagram `Connect` starts Meta OAuth.
- [ ] OAuth callback returns to `/dashboard/integrations`.
- [ ] Connected account card shows username, account type, and Page name.
- [ ] `Create Reel` form accepts prompt and non-sensitive image.
- [ ] Generated script, storyboard, caption, and hashtags appear.
- [ ] Render job completes.
- [ ] Rendered output is an MP4.
- [ ] Rendered MP4 is vertical 9:16.
- [ ] Video preview works in the browser.
- [ ] Publish flow tested with a non-sensitive test Reel.
- [ ] Schedule flow tested, if included in the screencast.
- [ ] Publish History shows job status.

## API Call Evidence

- [ ] Required API calls are performed from AI Reel Studio, not only Graph API
      Explorer.
- [ ] OAuth token exchange occurs through the backend.
- [ ] Page/Instagram account resolution occurs through the backend.
- [ ] Media container creation occurs through the backend worker in live mode.
- [ ] Media publish occurs through the backend worker in live mode.
- [ ] Publish job status is visible in the app UI.

## Security And Privacy

- [ ] Token encryption is enabled.
- [ ] Logs do not expose access tokens.
- [ ] UI does not expose access tokens.
- [ ] Screencast does not expose tokens, secrets, env files, database consoles,
      or real customer data.
- [ ] Privacy policy matches the actual data flows.
- [ ] Data deletion instructions are public.
- [ ] Reviewer test media is non-sensitive.

## Screencast And Submission Notes

- [ ] Screencast uploaded to `<screencast-video-url>`.
- [ ] Screencast follows `SCREENCAST_SCRIPT.md`.
- [ ] Screencast matches the written review notes.
- [ ] Submission notes include test credentials and exact reviewer steps.
- [ ] Troubleshooting notes are included.
- [ ] The final submission clearly states AI Reel Studio does not access DMs,
      comments, ads, or unrelated Page data.
