# Reviewer Test Credentials Template

Use this file as the source of truth when filling the Meta App Review test
credentials form. Replace every placeholder before submission.

## Staging App

- Staging frontend URL: `https://<staging-app-domain>`
- Staging API URL: `https://<staging-api-domain>`
- Privacy policy URL: `https://<staging-app-domain>/privacy`
- Data deletion URL or instructions: `https://<staging-app-domain>/privacy/delete-data`

## AI Reel Studio Login

- Email: `<reviewer-test-email>`
- Password: `<reviewer-test-password>`
- Workspace name: `<reviewer-test-workspace-name>`

The reviewer account should have enough usage quota to create, render, publish,
and schedule at least one non-sensitive test Reel.

## Facebook Test User Requirements

- Facebook test user email or ID: `<facebook-test-user-email-or-id>`
- The Facebook test user must be able to complete Meta OAuth.
- The Facebook test user must have access to the test Facebook Page.
- The test user should not rely on localhost, mock mode, Graph API Explorer, or
  developer-only manual token creation.

## Facebook Page Requirements

- Facebook Page name: `<facebook-page-name>`
- Facebook Page ID: `<facebook-page-id>`
- Reviewer user's Page role/access: `<admin-or-full-control-access>`
- Page must be selected or granted during the Meta OAuth prompt.

## Instagram Professional Account Requirements

- Instagram username: `@<instagram-business-or-creator-username>`
- Instagram account type: `<Business-or-Creator>`
- Linked Facebook Page: `<facebook-page-name>`

Personal Instagram accounts are not supported by the Instagram Graph API
publishing flow. The Instagram account must be Business or Creator and linked to
a Facebook Page.

## Known Limitations For Review

- Localhost and mock mode are not valid for Meta App Review.
- Reviewers must use the live HTTPS staging app.
- The app does not request or use Instagram DMs, comments, ads, insights, or
  unrelated Facebook Page data.
- The publish button is available only after a Reel has a rendered MP4.
- Live Instagram publishing requires a public HTTPS video URL.
- If scheduling is used, the scheduled time must be in the future.
