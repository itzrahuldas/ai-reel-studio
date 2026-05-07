# Privacy Policy Checklist

Before Meta App Review submission, confirm the public privacy policy URL is
complete and accessible without login.

## Public Access

- [ ] Privacy policy URL loads over HTTPS without login.
- [ ] URL is entered in the Meta app dashboard.
- [ ] Page is not blocked by robots, basic auth, IP allowlists, or staging
      password protection.
- [ ] Company/app name matches the Meta app name and AI Reel Studio branding.
- [ ] Contact email is present: `<privacy-contact-email>`.

## Data Disclosure

- [ ] Explains what AI Reel Studio does.
- [ ] Explains Instagram/Facebook data used:
      - Instagram professional account ID
      - Instagram username
      - account type
      - linked Facebook Page ID/name
      - OAuth token for publishing
      - published media ID/job status
- [ ] Explains user-provided data:
      - account profile
      - workspace
      - prompt
      - uploaded image
      - generated script/storyboard/caption/hashtags
      - rendered MP4
      - scheduling/publishing choices
- [ ] Explains generated media storage.
- [ ] Explains token storage and encryption at rest.
- [ ] Explains that tokens are not sold, displayed publicly, or returned to the
      frontend.
- [ ] Explains that AI Reel Studio does not access DMs, comments, ads, or
      unrelated Page data.

## Processors And Sharing

- [ ] Explains no sale of user data.
- [ ] Lists hosting provider: `<hosting-provider>`.
- [ ] Lists storage provider: `<storage-provider>`.
- [ ] Lists email/support provider if used: `<support-provider>`.
- [ ] Lists OpenAI or AI provider if enabled: `<ai-provider-name-or-not-enabled>`.
- [ ] Lists Stripe if billing is enabled: `<stripe-enabled-or-not-enabled>`.
- [ ] Explains data is shared with Meta only when the user connects Instagram
      and publishes/schedules content.

## User Rights And Retention

- [ ] Explains how users can disconnect Instagram.
- [ ] Explains how users can request account/data deletion.
- [ ] Links to data deletion instructions:
      `https://<staging-app-domain>/privacy/delete-data`.
- [ ] Defines retention period placeholders:
      - account/workspace data: `<retention-period>`
      - generated media: `<retention-period>`
      - publish jobs: `<retention-period>`
      - security/legal logs: `<security-log-retention-period>`
- [ ] Explains legal/security exceptions for retained logs.
- [ ] Explains how users can contact support:
      `<privacy-contact-email>`.

## Review Readiness

- [ ] Policy text is consistent with `PERMISSION_JUSTIFICATIONS.md`.
- [ ] Policy does not claim access to permissions the app does not request.
- [ ] Policy covers OAuth token encryption.
- [ ] Policy covers generated media deletion.
- [ ] Policy is linked from the app footer or another public location.
