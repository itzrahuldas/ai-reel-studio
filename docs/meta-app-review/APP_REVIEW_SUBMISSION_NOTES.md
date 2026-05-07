# App Review Submission Notes

Copy the sections below into the Meta App Review submission and replace all
placeholders before submitting.

## Short App Description

AI Reel Studio lets a user generate an Instagram Reel from a text prompt and an
optional reference image, review the generated script/storyboard/caption,
render a vertical 9:16 MP4, and publish or schedule that Reel to a connected
Instagram Business or Creator account through the official Instagram Graph API.

## Requested Permissions

We are requesting only the permissions needed for the reviewer flow:

- `instagram_basic`: identifies the connected Instagram professional account and
  displays username/account type in AI Reel Studio.
- `instagram_content_publish`: publishes the rendered MP4 Reel to the connected
  Instagram professional account.
- `pages_show_list`: lists/resolves Facebook Pages available to the reviewer so
  AI Reel Studio can identify the Page linked to the Instagram Business or
  Creator account.

`pages_read_engagement` is not requested unless the deployed OAuth/API flow
requires it for Page metadata lookup. AI Reel Studio does not read Page
engagement metrics or insights.

AI Reel Studio does not access Instagram DMs, Instagram comments, ads, Business
Manager assets, Facebook Page posts, or unrelated Facebook Page data.

## Test Credentials

- Staging app URL: `https://<staging-app-domain>`
- API URL: `https://<staging-api-domain>`
- App email: `<reviewer-test-email>`
- App password: `<reviewer-test-password>`
- Facebook test user: `<facebook-test-user-email-or-id>`
- Facebook Page: `<facebook-page-name>`
- Linked Instagram professional account: `@<instagram-business-or-creator-username>`

The Facebook test user has access to the Facebook Page, and the Page is linked
to the Instagram Business or Creator account.

## Screencast

- Screencast URL: `<screencast-video-url>`

The screencast shows the complete end-to-end flow through AI Reel Studio:
login, Instagram connection through Meta OAuth, connected account display, Reel
creation, generated script/storyboard/caption/hashtags, MP4 render preview,
publish or schedule action, and publish job status/history.

## Step-By-Step Reviewer Instructions

1. Open `https://<staging-app-domain>`.
2. Click `Sign In`.
3. Log in with `<reviewer-test-email>` and `<reviewer-test-password>`.
4. Open `Dashboard` > `Integrations`.
5. Click `Connect` on the Instagram card.
6. Complete Meta OAuth with the Facebook test user and grant Page access.
7. Confirm AI Reel Studio returns to the Integrations page and shows the
   connected Instagram account card.
8. Open `Dashboard` > `Create`.
9. Enter a safe test prompt, for example:
   `Create a short product Reel for a small coffee shop promoting a new iced latte.`
10. Upload a non-sensitive image or use the existing test project.
11. Click `Generate Reel`.
12. On the Reel detail page, confirm the script, storyboard, caption, hashtags,
    and generation timeline are visible.
13. Click `Render Video`.
14. Confirm the `Video Preview` card displays a vertical MP4 after rendering.
15. In `Instagram Publishing`, select the connected Instagram account.
16. Click `Publish Now`, or click `Schedule`, choose a future date/time, and
    click `Confirm Schedule`.
17. Confirm `Publish History` shows the publish job status.

## Troubleshooting

- If no Page appears in OAuth, confirm the reviewer Facebook user has Page admin
  or full-control access and selected the Page in the OAuth prompt.
- If no Instagram account appears, confirm the Page is linked to an Instagram
  Business or Creator account.
- If the publish button is disabled, render a Reel first.
- If publishing fails, confirm the rendered MP4 URL is public HTTPS in staging.
- If OAuth fails, confirm the OAuth redirect URI in Meta exactly matches the
  staging callback URL.
- Localhost and mock mode are not valid for review.

## Privacy And Deletion

- Privacy policy URL: `https://<staging-app-domain>/privacy`
- Data deletion URL or instructions:
  `https://<staging-app-domain>/privacy/delete-data`
- Support email: `<privacy-contact-email>`

No real tokens, secrets, client secrets, app secrets, encryption keys, or real
customer data are included in the screencast or submission notes.
