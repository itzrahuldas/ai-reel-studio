# ADR-0002: Instagram API Strategy

**Status:** Accepted
**Date:** 2026-05-03
**Deciders:** Instagram Integration Engineer, Security Engineer, System Architect

---

## Context

We need to publish Instagram Reels on behalf of users. There are several approaches available:

1. Official Meta Graph API (Reels publishing)
2. Unofficial browser automation / scraping
3. Third-party scheduling SaaS APIs

## Decision

**Use only the official Meta Graph API v21.0 via OAuth 2.0.**

Specifically:
- User connects their Instagram Business Account via Meta OAuth
- We request only the minimum required permissions
- Access tokens stored encrypted in PostgreSQL
- Publishing via: create container → poll status → publish media

## Consequences

**Positive:**
- Compliant with Meta's Terms of Service
- No risk of account bans or legal action
- Token-based — no passwords stored
- Stable API with versioning guarantees

**Negative:**
- Requires Meta App Review (2–6 weeks) for production
- Requires Instagram Business Account (not personal)
- Rate limited to 25 posts/day per account
- Container processing can take 1–5 minutes (requires polling)
- App must maintain Business Verification

## Alternatives Considered

- **Browser automation (Puppeteer/Playwright)**: REJECTED — violates Meta ToS, risk of bans, brittle
- **Unofficial Python bots (instagrapi, etc.)**: REJECTED — not production safe, illegal for commercial use
- **Third-party APIs (Later, Buffer)**: REJECTED — creates dependency on third party, additional cost layer, no control

## Compliance Notes

- Polling implementation must respect rate limits
- NEVER store user Instagram credentials (username/password)
- Token expiry must be monitored proactively
- All publish attempts must be logged in audit_logs
