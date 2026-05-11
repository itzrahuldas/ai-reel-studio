# Screencast Script

Target length: about five minutes. Record the live HTTPS staging app, not
localhost. Use the reviewer test account and a non-sensitive test image/prompt.
Do not show real access tokens, app secrets, client secrets, encryption keys,
database consoles, terminal env output, or real customer data.

## 0:00 - App Intro And Purpose

Narration:
"This is AI Reel Studio. It helps a user create an Instagram Reel from a prompt
and optional image, render a vertical MP4, then publish or schedule the Reel to a
connected Instagram Business or Creator account using the official Instagram
Graph API."

Action:
Open `https://<staging-app-domain>`. Show the public landing page title and the
`Sign In` button.

## 0:20 - Login With Reviewer Account

Narration:
"I am logging in with the reviewer test account provided in the submission
notes."

Action:
Click `Sign In`. Enter:

- email: `<reviewer-test-email>`
- password: `<reviewer-test-password>`

Click the login submit button. Show the dashboard after login succeeds.

## 0:40 - Navigate To Integrations

Narration:
"The Integrations page is where the user connects an Instagram professional
account."

Action:
Navigate to `Dashboard` > `Integrations`. Show the Instagram card and the
`Connect` button.

## 1:00 - Click Connect Instagram

Narration:
"The Connect button starts the Meta OAuth flow. The app redirects the user to
Meta and does not expose tokens in the browser UI."

Action:
Click `Connect` on the Instagram card.

## 1:20 - Show Meta OAuth Permissions

Narration:
"The OAuth prompt requests only the permissions needed to identify the linked
Instagram professional account, resolve the Facebook Page connection, and publish
the rendered Reel."

Action:
Show the Meta OAuth permission prompt. The prompt should include the requested
permissions documented in `PERMISSION_JUSTIFICATIONS.md`. Continue with the
Facebook test user and grant access to the test Page.

## 1:45 - Show Connected Account Card

Narration:
"After OAuth, the app returns to AI Reel Studio and shows the connected
Instagram account metadata. The app stores the token encrypted on the backend
and does not display it."

Action:
Return to `/dashboard/integrations`. Show the connected Instagram card:

- username
- account type
- linked Facebook Page
- reconnect/disconnect controls

## 2:10 - Create Reel With Prompt And Image

Narration:
"Now I will create a new Reel. The user provides the idea, optional reference
image, language, tone, duration, and optional call to action."

Action:
Navigate to `Dashboard` > `Create`. Upload a non-sensitive test image or use a
preloaded sample. Enter:

`Create a short product Reel for a small coffee shop promoting a new iced latte.`

Select language, tone, duration, and CTA. Click `Generate Reel`.

## 2:50 - Show Generated Script, Storyboard, Caption, And Hashtags

Narration:
"The app generated the creative plan for the Reel. This includes the script,
storyboard scenes, caption, hashtags, and generation timeline."

Action:
On the Reel detail page, show:

- `Generated Content`
- `Script`
- `Storyboard`
- `Caption`
- `Hashtags`
- `Generation Timeline`

## 3:20 - Render Video

Narration:
"Before publishing, the Reel must be rendered into a vertical MP4."

Action:
Click `Render Video`. Show the rendering banner and the render timeline while it
is running.

## 3:50 - Preview Rendered MP4

Narration:
"The rendered output is a 9:16 MP4 preview that the user can review before
publishing."

Action:
Show the `Video Preview` card with the MP4 player controls. Play a few seconds
of the test Reel.

## 4:10 - Publish Or Schedule To Instagram

Narration:
"Once the MP4 exists, the Instagram Publishing section lets the user publish now
or schedule a future publish for the connected Instagram account."

Action:
In `Instagram Publishing`, show the connected account. Either:

- click `Publish Now`, or
- click `Schedule`, pick a future date/time, and click `Confirm Schedule`.

Use whichever option is safest for the test Instagram account.

## 4:40 - Show Publish Job Status Timeline

Narration:
"The Publish History section shows the job status. For immediate publishing, the
backend creates an Instagram media container, polls for processing, and publishes
when Meta marks the container ready. For scheduled publishing, the job remains
scheduled until the selected time."

Action:
Show `Publish History` with status such as queued, container created, polling,
published, scheduled, or failed. If published, show the resulting media ID. Do
not show tokens or secrets.

## 5:00 - Explain Data Deletion And Privacy Links

Narration:
"The app provides privacy and data deletion instructions. A user can request
deletion of profile, workspace, OAuth tokens, connected social account records,
generated projects, media assets, and publish jobs."

Action:
Show the privacy policy URL and data deletion URL or support email placeholders:

- `https://<staging-app-domain>/privacy`
- `https://<staging-app-domain>/privacy/delete-data`
- `<privacy-contact-email>`
