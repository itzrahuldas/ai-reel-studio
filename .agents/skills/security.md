# Skill: Security

## No Secrets in Code
- NEVER hardcode: API keys, passwords, tokens, encryption keys
- NEVER commit: .env files, *.pem, *.key files
- NEVER log: access tokens, user passwords, encryption keys
- .gitignore must include: .env, .env.local, .env.production, *.pem, *.key

## Encryption Requirement
- Instagram tokens: AES-256-GCM encrypted before storage
- JWT signing: use SECRET_KEY (min 32 bytes random)
- TOKEN_ENCRYPTION_KEY: 32-byte key (64 hex chars), rotatable

## OAuth Safety
- CSRF state token: required, validated on every OAuth callback
- State token signed with SECRET_KEY, 10-minute TTL
- Authorization code: exchanged immediately, single-use
- No token stored in browser (only in encrypted DB column)

## Upload Validation
- Validate MIME type from Content-Type header
- Validate magic bytes (first 512 bytes of file) match declared type
- Max file size enforced both client-side (UX) and server-side (security)
- Allowed types: image/jpeg, image/png, image/webp only
- Reject executables, scripts, archives

## Rate Limiting
- Apply slowapi limits to all public endpoints
- Stricter limits on auth endpoints (login, register)
- Instagram publish: respect 25/day limit per account
- Store rate limit counters in Redis

## Logging Redaction
- Create SafeLogger wrapper that auto-redacts sensitive fields
- Redacted fields: 	oken, ccess_token, password, secret, key
- Correlation ID (request_id) in every log line

## Abuse Prevention
- Failed login attempts: lock account for 15 min after 5 failures
- Generation limit: configurable per workspace tier
- Upload limit: enforced per user per hour
- Content moderation: 3 flags ? account flagged for manual review
