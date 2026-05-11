# Final Meta Submission Runbook

Use this runbook immediately before submitting AI Reel Studio for Meta App
Review. Keep the submission focused on the permissions demonstrated in the
screencast:

- `instagram_basic`
- `instagram_content_publish`
- `pages_show_list`

Do not request `pages_read_engagement` for the current submission.

## 1. Confirm Source Of Truth

1. Confirm the branch is current:
   `chore/staging-deployment-setup`.
2. Confirm the latest scope alignment commit is present:
   `9b2eebe fix(meta): align Instagram OAuth review scopes`.
3. Confirm backend OAuth scopes are exactly:
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`.
4. Confirm `docs/meta-app-review/PERMISSION_JUSTIFICATIONS.md`,
   `APP_REVIEW_SUBMISSION_NOTES.md`, and `META_APP_REVIEW_PACKAGE.md` all list
   the same three requested permissions.
5. Confirm `pages_read_engagement` appears only as a "do not request yet"
   permission.

## 2. Fill Placeholders

Replace all placeholder values before submission:

- [ ] `https://<staging-app-domain>`
- [ ] `https://<staging-api-domain>`
- [ ] `<reviewer-test-email>`
- [ ] `<reviewer-test-password>`
- [ ] `<reviewer-test-workspace-name>`
- [ ] `<facebook-test-user-email-or-id>`
- [ ] `<facebook-page-name>`
- [ ] `<facebook-page-id>`
- [ ] `@<instagram-business-or-creator-username>`
- [ ] `<privacy-contact-email>`
- [ ] `<screencast-video-url>`
- [ ] `<company-legal-name>`
- [ ] `<retention-period>`
- [ ] `<security-log-retention-period>`
- [ ] `<hosting-provider>`
- [ ] `<storage-provider>`
- [ ] `<ai-provider-name-or-not-enabled>`
- [ ] `<stripe-enabled-or-not-enabled>`

Do not paste real access tokens, app secrets, client secrets, webhook secrets,
database URLs with passwords, encryption keys, or real customer data into Meta
App Review fields.

## 3. Verify Live HTTPS Staging

1. Open `https://<staging-app-domain>` in a private browser session.
2. Confirm the landing page loads without login.
3. Confirm `https://<staging-api-domain>/health` or the deployed health endpoint
   responds successfully.
4. Log in with `<reviewer-test-email>`.
5. Confirm Dashboard, Integrations, Create Reel, and Reel detail pages load.
6. Confirm the browser uses HTTPS for app, API, media preview, privacy policy,
   and deletion instructions.
7. Confirm staging is not in localhost mode.
8. Confirm staging is not using Instagram mock mode for review.
9. Confirm generated media URLs used for Instagram publishing are public HTTPS
   URLs reachable by Meta.

## 4. Verify OAuth Redirect URI

In the Meta app dashboard, verify:

- [ ] OAuth redirect URI exactly matches:
      `https://<staging-api-domain>/api/v1/integrations/instagram/callback`
- [ ] App domain includes `<staging-app-domain>`.
- [ ] Site URL points to `https://<staging-app-domain>`.
- [ ] Valid OAuth redirect URIs do not include localhost.
- [ ] Meta product settings use the same app ID used by staging.
- [ ] OAuth prompt displays only:
      `instagram_basic`, `instagram_content_publish`, `pages_show_list`.

## 5. Prepare Facebook Test User, Page, And Instagram Account

1. Create or select a Facebook test user that Meta reviewers can use.
2. Grant the test user access to a Facebook Page.
3. Link that Page to an Instagram Business or Creator account.
4. Confirm the Instagram account is not a personal account.
5. Confirm the Facebook test user can select/grant the Page during OAuth.
6. Confirm the Page name and Instagram username match the placeholders in
   `REVIEWER_TEST_CREDENTIALS_TEMPLATE.md`.
7. Create a non-sensitive test Reel destination account and avoid customer or
   personal media.

## 6. Prepare Reviewer Account

1. Create `<reviewer-test-email>` in AI Reel Studio.
2. Set `<reviewer-test-password>` to a temporary reviewer-safe password.
3. Confirm the account has enough quota for:
   - one Reel generation
   - one render
   - one immediate publish
   - one scheduled publish, if the screencast shows scheduling
4. Confirm no real customer workspace or media is visible to the reviewer.

## 7. Record Screencast

Follow `SCREENCAST_SCRIPT.md` exactly:

- [ ] Show the public app URL.
- [ ] Log in with the reviewer account.
- [ ] Open `Dashboard` > `Integrations`.
- [ ] Click Instagram `Connect`.
- [ ] Show the Meta OAuth prompt.
- [ ] Confirm the prompt does not show `pages_read_engagement`.
- [ ] Show the connected account card.
- [ ] Create a Reel with a safe prompt and non-sensitive image.
- [ ] Show script, storyboard, caption, hashtags, and generation timeline.
- [ ] Render the video.
- [ ] Preview the 9:16 MP4.
- [ ] Publish now or schedule.
- [ ] Show Publish History.
- [ ] Show privacy and data deletion links.

Do not show terminal windows, `.env` files, app secrets, access tokens,
database consoles, production customer data, or real private URLs.

## 8. Upload Screencast

1. Upload the screencast to `<screencast-video-url>`.
2. Confirm the link is accessible to Meta reviewers without login.
3. Confirm the video quality clearly shows OAuth permissions and UI steps.
4. Confirm the video matches `APP_REVIEW_SUBMISSION_NOTES.md`.

## 9. Meta Dashboard Submission Checklist

In Meta App Review:

- [ ] Select only `instagram_basic`.
- [ ] Select only `instagram_content_publish`.
- [ ] Select only `pages_show_list`.
- [ ] Do not select `pages_read_engagement`.
- [ ] Paste the app description from `APP_REVIEW_SUBMISSION_NOTES.md`.
- [ ] Paste reviewer steps from `APP_REVIEW_SUBMISSION_NOTES.md`.
- [ ] Add reviewer credentials from `REVIEWER_TEST_CREDENTIALS_TEMPLATE.md`.
- [ ] Add the screencast URL.
- [ ] Add privacy policy URL.
- [ ] Add data deletion URL or public deletion instructions.
- [ ] Add troubleshooting notes.
- [ ] State that AI Reel Studio does not access DMs, comments, ads, Page posts,
      Page insights, or unrelated Page data.

## 10. What Not To Submit

Do not submit:

- localhost URLs
- mock mode flows
- Graph API Explorer-only evidence
- a personal Instagram account
- permissions not used in the screencast
- `pages_read_engagement`
- `instagram_manage_comments`
- `instagram_manage_messages`
- `ads_management`
- `business_management`
- `pages_manage_posts`
- real secrets or tokens
- real customer data

## 11. Final Pre-Submit Gate

Submit only when all are true:

- [ ] Staging login works.
- [ ] Meta OAuth completes with the reviewer Facebook test user.
- [ ] Connected account card appears.
- [ ] Create Reel works.
- [ ] Rendered MP4 preview works.
- [ ] Publish or schedule path is visible and functional.
- [ ] Publish History is visible.
- [ ] Privacy policy is public.
- [ ] Data deletion instructions are public.
- [ ] Screencast URL works.
- [ ] Meta dashboard permission selection matches backend scopes.
