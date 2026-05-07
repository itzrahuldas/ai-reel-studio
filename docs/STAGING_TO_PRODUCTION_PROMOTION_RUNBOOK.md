# Staging To Production Promotion Runbook

This runbook promotes a passing staging build to production. Commands are
examples; adapt them to the production deployment platform.

## 1. Pre-Promotion Gate

- [ ] Staging Docker stack is healthy.
- [ ] Full staging smoke test passed.
- [ ] Meta OAuth scopes are aligned:
      `instagram_basic`, `instagram_content_publish`, `pages_show_list`.
- [ ] `pages_read_engagement` is not requested.
- [ ] Production launch checklist has no unresolved critical blockers.
- [ ] Production environment values are ready in the secret manager.
- [ ] Rollback owner is assigned.

## 2. Merge Branch Flow

1. Ensure `chore/staging-deployment-setup` is pushed.
2. Open a pull request into the production branch:
   `<production-branch-name>`.
3. Confirm CI passes.
4. Review docs, migration notes, and deployment changes.
5. Merge using the repository's approved merge strategy.
6. Do not force push production branches.

## 3. CI Checks

Required checks before deploy:

- [ ] Backend lint passes.
- [ ] Backend tests pass.
- [ ] Frontend lint/typecheck/build pass.
- [ ] Docker images build.
- [ ] Migration checks pass.
- [ ] No secret scanning alerts are open.

## 4. Tag And Release Recommendation

After merge:

```bash
git checkout <production-branch-name>
git pull origin <production-branch-name>
git tag -a v<version> -m "AI Reel Studio production release v<version>"
git push origin v<version>
```

Use the tag or immutable commit SHA as the production image label.

## 5. Build Images

Build production images for:

- `web`
- `api`
- `worker-generation`
- `worker-rendering`
- `worker-publishing`
- `celery-beat`

Checklist:

- [ ] Images are built from the release tag or SHA.
- [ ] Images are pushed to the production registry.
- [ ] Image digest is recorded.
- [ ] Build logs do not expose secrets.

## 6. Apply Migrations

Before starting new application containers:

1. Pause or drain workers if required by the platform.
2. Take a production database backup.
3. Run Alembic migrations:

   ```bash
   alembic upgrade head
   ```

4. Verify the migration completed.
5. Record migration timestamp and release SHA.

## 7. Start Services

Start or update services in this order:

1. API
2. Web
3. `worker-generation`
4. `worker-rendering`
5. `worker-publishing`
6. `celery-beat`

Verify:

- [ ] API is healthy.
- [ ] Web is healthy.
- [ ] Workers are connected to Redis.
- [ ] Exactly one `celery-beat` is running.
- [ ] Queue depth is stable.

## 8. Production Smoke Test

Run smoke checks with production URLs and a non-sensitive test account:

```bash
SMOKE_API_BASE_URL=https://<production-api-domain> \
SMOKE_FRONTEND_BASE_URL=https://<production-app-domain> \
SMOKE_TEST_EMAIL=<production-smoke-test-email> \
SMOKE_TEST_PASSWORD=<production-smoke-test-password> \
SMOKE_CREATE_REEL=true \
SMOKE_TEST_STRIPE_MOCK=false \
SMOKE_TEST_INSTAGRAM_MOCK=false \
python scripts/staging_smoke_test.py
```

Do not use real customer data in smoke tests.

## 9. Verify Stripe Webhook

- [ ] Production Stripe webhook endpoint is public HTTPS.
- [ ] Webhook secret matches production env.
- [ ] Test event is delivered successfully.
- [ ] Checkout success URL works.
- [ ] Checkout cancel URL works.
- [ ] Customer Portal return URL works.
- [ ] Logs do not expose Stripe secrets.

## 10. Verify Meta OAuth Callback

- [ ] Meta app dashboard uses production callback URL:
      `https://<production-api-domain>/api/v1/integrations/instagram/callback`
- [ ] OAuth prompt shows only:
      `instagram_basic`, `instagram_content_publish`, `pages_show_list`.
- [ ] OAuth completes with a test Facebook user.
- [ ] Connected Instagram card appears in production.
- [ ] `pages_read_engagement` does not appear in the prompt.

## 11. Verify Media Public URLs

- [ ] Rendered MP4 URL is public HTTPS.
- [ ] Meta can fetch the MP4 URL.
- [ ] Browser preview works.
- [ ] Bucket does not allow public listing.
- [ ] Test publish creates or schedules a publish job.

## 12. Verify Logs Are Secret-Safe

Search logs for accidental exposure:

- [ ] access tokens
- [ ] authorization headers
- [ ] app secrets
- [ ] API keys
- [ ] webhook secrets
- [ ] database passwords
- [ ] encryption keys

If any secret is exposed, rotate the secret and fix logging before launch.

## 13. Rollback Checklist

If launch fails:

1. Stop or pause new publish jobs if needed.
2. Roll back web/API/workers/beat to previous image digest.
3. Confirm API and web health.
4. Confirm workers process or safely ignore existing jobs.
5. If database rollback is needed, follow the migration rollback plan.
6. Notify stakeholders with the current status.
7. Preserve logs for incident review.

Example placeholders:

```bash
deployctl rollback web --image <previous-web-image-digest>
deployctl rollback api --image <previous-api-image-digest>
deployctl rollback worker-generation --image <previous-worker-image-digest>
deployctl rollback worker-rendering --image <previous-worker-image-digest>
deployctl rollback worker-publishing --image <previous-worker-image-digest>
deployctl rollback celery-beat --image <previous-beat-image-digest>
```

Use the actual platform commands for production.

## 14. Promotion Sign-Off

- [ ] Release SHA: `<release-sha>`
- [ ] Release tag: `<release-tag>`
- [ ] Migration completed at: `<timestamp>`
- [ ] Smoke test completed at: `<timestamp>`
- [ ] Launch owner: `<launch-owner>`
- [ ] Rollback owner: `<rollback-owner>`
- [ ] Production status: `<go-or-no-go>`
