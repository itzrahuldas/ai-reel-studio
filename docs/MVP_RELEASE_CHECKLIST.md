# MVP Release Checklist

## 1. Local Setup Checklist
- [x] Configure `.env` with `DATABASE_URL`, `REDIS_URL`, and `SECRET_KEY`.
- [x] Configure `.env` with `TOKEN_ENCRYPTION_KEY` (must be 64-character hex).
- [x] Verify `INSTAGRAM_INTEGRATION_MODE="mock"` is active for safe local development.
- [x] Validate `docker-compose up` cleanly builds `api`, `worker`, and `postgres` services.

## 2. Staging Deployment Checklist
- [ ] Deploy PostgreSQL and Redis managed instances.
- [ ] Apply Alembic Migrations against the Staging database.
- [ ] Configure `APP_ENV="staging"`.
- [ ] Configure `API_PUBLIC_BASE_URL` with public HTTPS domain.
- [ ] Spin up Celery worker instances (`celery -A app.main worker`).
- [ ] Ensure `META_APP_ID` and `META_APP_SECRET` point to Meta Test App.

## 3. Production Deployment Checklist
- [ ] Ensure all mock flags are explicitly toggled off (`INSTAGRAM_INTEGRATION_MODE="live"`).
- [ ] Configure production-grade Cloudflare/Nginx proxy for Web and API instances.
- [ ] Enforce CORS specifically matching the `FRONTEND_URL`.
- [ ] Setup persistent Volumes/S3 mappings for `MediaAsset` local storage paths.
- [ ] Validate proper production credentials for Meta Graph API integration.

## 4. Meta App Review Checklist
- [ ] Ensure Application is verified as a Business.
- [ ] Configure the correct `META_REDIRECT_URI` matching production SSL.
- [ ] Submit requests for `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement` scopes.
- [ ] Produce walkthrough video required by Meta for App Review demonstrating the login & publish flow.

## 5. Storage / Public URL Checklist
- [x] The application handles absolute URLs and local file system mounts securely without OS traversal risks.
- [ ] If using AWS S3, verify `S3_ENDPOINT_URL`, `S3_BUCKET`, and `STORAGE_PROVIDER="s3"` are configured in `.env`.

## 6. Security Checklist
- [x] Token Encryption Key mapped globally for Fernet interactions.
- [x] JWT algorithms mapped for access/refresh validations.
- [x] Workspace enforcement is absolute across all critical read/write queries.
- [x] API outputs strictly filter access tokens from Meta errors (`normalize_meta_error` concepts integrated implicitly in `InstagramClient._raise_for_error`).

## 7. Launch Readiness Status
- **Status:** READY FOR RELEASE (MVP Level 1).
- **Recommendation:** Can safely ship to staging/beta clients immediately to validate end-to-end rendering logic without Advanced Editor enhancements.
