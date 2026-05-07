# Data Deletion Instructions

AI Reel Studio must provide public data deletion instructions for users and Meta
reviewers. Use the hosted deletion page if it exists; otherwise use the email
method until the page is implemented.

## User-Facing Deletion Method

Preferred public URL:

`https://<staging-app-domain>/privacy/delete-data`

If that page is not implemented yet, publish these instructions on a public
privacy page and provide the support email:

`<privacy-contact-email>`

Suggested user instructions:

1. Send an email to `<privacy-contact-email>` from the email address used for
   the AI Reel Studio account.
2. Use the subject: `AI Reel Studio data deletion request`.
3. Include the AI Reel Studio account email and, if relevant, the connected
   Instagram username.
4. Support will verify the request and delete eligible account data within
   `<deletion-sla-days>` days.
5. The user can also disconnect Instagram from `Dashboard` > `Integrations`.

## Reviewer-Facing Deletion Instructions

Meta reviewers can verify deletion support by visiting:

`https://<staging-app-domain>/privacy/delete-data`

or by sending a test request to:

`<privacy-contact-email>`

Use the reviewer account:

- AI Reel Studio email: `<reviewer-test-email>`
- Instagram username: `@<instagram-business-or-creator-username>`

## Data Deleted

When a verified deletion request is processed, delete or anonymize:

- user profile
- workspace membership
- workspace records owned only by the deleted user
- OAuth tokens
- social account records
- generated Reel projects
- generated scripts/storyboards/captions/hashtags
- uploaded reference images
- rendered media assets
- render jobs
- publish jobs
- scheduled publish jobs that have not executed
- app-level usage records tied to the user, where deletion is legally allowed

## Data That May Be Retained

AI Reel Studio may retain limited records when required for legal, tax,
security, fraud prevention, abuse prevention, or operational audit purposes.
Examples:

- payment records required by law, if billing is enabled
- security logs
- abuse/fraud prevention logs
- minimal deletion-request audit trail

Retention period placeholder:

`<security-or-legal-log-retention-period>`

Retained records should not include active OAuth access tokens unless legally
required. OAuth tokens should be revoked or deleted during account deletion.

## Manual Support Contact

- Support email: `<privacy-contact-email>`
- Company/legal name: `<company-legal-name>`
- App name: `AI Reel Studio`
- Expected response time: `<support-response-time>`
- Expected deletion completion time: `<deletion-sla-days>` days

## Implementation Notes

- Do not expose real tokens or secrets in deletion emails.
- Verify request ownership before deleting data.
- Record a minimal audit event for deletion completion.
- Cancel scheduled publish jobs during deletion.
- Confirm deletion completion to the requester.
