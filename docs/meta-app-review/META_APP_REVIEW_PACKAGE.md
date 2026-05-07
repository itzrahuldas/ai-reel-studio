# Meta App Review Package

## Overview

AI Reel Studio is a web application that helps a user generate, review, render,
and publish Instagram Reels from a text prompt and an optional reference image.
The app uses Meta OAuth so a user can connect an Instagram Business or Creator
account that is linked to a Facebook Page. After the user creates and renders a
9:16 MP4 Reel, the app can publish immediately or schedule a publish job through
the Instagram Graph API.

This package is written for Meta App Review. It describes the exact reviewer
flow, required test setup, requested permissions, privacy/deletion notes, and QA
checks needed before submission.

## Staging URLs

- FRONTEND_URL: `https://<staging-app-domain>`
- API_URL: `https://<staging-api-domain>`
- Privacy policy URL: `https://<staging-app-domain>/privacy`
- Data deletion URL or instructions: `https://<staging-app-domain>/privacy/delete-data`

Do not submit localhost URLs for Meta review. The reviewer should use the live
HTTPS staging deployment only.

## Reviewer Test Account

- App email: `<reviewer-test-email>`
- App password: `<reviewer-test-password>`
- Facebook test user: `<facebook-test-user-email-or-id>`
- Facebook test Page: `<facebook-page-name>`
- Linked Instagram professional account: `@<instagram-business-or-creator-username>`

No real tokens, app secrets, client secrets, access tokens, encryption keys, or
real customer data should be included in the submission notes or screencast.

## Required Tester Setup

Before review, ensure the Facebook test user has access to a Facebook Page. The
Page must be linked to an Instagram Business or Creator account. Personal
Instagram accounts are not supported by the Instagram Graph API publishing flow.

The test user should be able to complete Meta OAuth, grant the requested
permissions, and return to AI Reel Studio with a connected Instagram account
card visible in the Integrations page.

## Permission Recommendation

Request only the permissions demonstrated in the reviewer flow:

- `instagram_basic`
- `instagram_content_publish`
- `pages_show_list`

`pages_read_engagement` should be requested only if the deployed OAuth and Page
lookup flow still requires it to read Page metadata while resolving the linked
Instagram Business account. AI Reel Studio does not use Page engagement metrics,
insights, comments, DMs, ads, Page post management, or Business Manager
administration. If the Page lookup works with `pages_show_list` alone, mark
`pages_read_engagement` as "do not request yet" in the Meta submission.

## Exact User Flow For Review

1. Open `https://<staging-app-domain>`.
2. Click `Sign In`.
3. Log in with:
   - email: `<reviewer-test-email>`
   - password: `<reviewer-test-password>`
4. Navigate to `Dashboard` > `Integrations`.
5. Click the Instagram `Connect` button.
6. Complete the Meta OAuth prompt using the Facebook test user.
7. Grant the requested permissions.
8. Confirm the browser returns to `/dashboard/integrations`.
9. Verify the connected Instagram account card shows:
   - Instagram username
   - account type
   - linked Facebook Page name
   - reconnect/disconnect controls
10. Navigate to `Dashboard` > `Create`.
11. Enter a safe test prompt, for example:
    `Create a short product Reel for a small coffee shop promoting a new iced latte.`
12. Upload a non-sensitive test image, or continue without an image if the
    reviewer account has a preloaded sample project.
13. Choose language, tone, duration, and optional CTA.
14. Click `Generate Reel`.
15. On the Reel detail page, wait for generated content.
16. Verify the page displays:
    - generated script
    - storyboard scenes
    - caption
    - hashtags
    - generation timeline
17. Click `Render Video`.
18. Wait for rendering to complete.
19. Verify the `Video Preview` card displays a vertical 9:16 MP4 video with
    browser playback controls.
20. In `Instagram Publishing`, select the connected Instagram account.
21. Click `Publish Now`, or click `Schedule`, choose a future date/time, and
    click `Confirm Schedule`.
22. Verify the `Publish History` section shows the publish job status timeline.
23. If publishing immediately, wait for statuses such as queued, container
    created, polling, and published.
24. If scheduling, verify the scheduled date/time is shown and the cancel action
    is available.

## What Reviewers Should See

- Successful login to AI Reel Studio.
- Instagram connect button on the Integrations page.
- Meta OAuth permission prompt for the requested permissions.
- Connected Instagram account card with username/account metadata.
- Create Reel form with prompt, reference image upload, language, tone, duration,
  and CTA fields.
- Generated storyboard, script, caption, hashtags, and status timelines.
- Rendered vertical 9:16 MP4 preview.
- Publish or schedule controls once a rendered MP4 is available.
- Publish job status timeline/history showing the job state and media ID after
  successful publish.

## Data Handling Summary

AI Reel Studio stores the minimum data needed to provide the product:

- app user profile and workspace membership
- connected Instagram account metadata
- encrypted OAuth access token
- generated Reel project data
- uploaded reference images and rendered MP4 assets
- render and publish job records
- audit and operational logs

OAuth tokens are encrypted at rest and are not returned to the frontend. Tokens
and secrets are not shown in the UI, logs, screencast, or documentation.

## Troubleshooting For Reviewers

- If no Facebook Page appears, confirm the Facebook test user has access to the
  Page and granted Page access in the OAuth prompt.
- If no Instagram account appears, confirm the Facebook Page is linked to an
  Instagram Business or Creator account.
- If the publish button is disabled, render a Reel first.
- If publishing fails in live mode, confirm the rendered MP4 URL is public HTTPS.
- If OAuth fails, confirm the staging OAuth redirect URI exactly matches the
  Meta app dashboard configuration.

## Reference Documentation

- Permission justifications: `docs/meta-app-review/PERMISSION_JUSTIFICATIONS.md`
- Reviewer credentials template: `docs/meta-app-review/REVIEWER_TEST_CREDENTIALS_TEMPLATE.md`
- Screencast script: `docs/meta-app-review/SCREENCAST_SCRIPT.md`
- Privacy checklist: `docs/meta-app-review/PRIVACY_POLICY_CHECKLIST.md`
- Data deletion instructions: `docs/meta-app-review/DATA_DELETION_INSTRUCTIONS.md`
- Copy-paste submission notes: `docs/meta-app-review/APP_REVIEW_SUBMISSION_NOTES.md`
- Pre-submission QA checklist: `docs/meta-app-review/QA_CHECKLIST_BEFORE_SUBMISSION.md`

Official Meta references:

- Meta App Review: `https://developers.facebook.com/docs/app-review/`
- Meta Permissions Reference: `https://developers.facebook.com/docs/permissions/`
- Instagram content publishing:
  `https://developers.facebook.com/docs/instagram-platform/content-publishing/`
