# Security — AI Reel Studio

**Version:** 0.1.0
**Last Updated:** 2026-05-03

---

## 1. Secret Management

- **Never hardcode secrets** in source code, config files, or Docker images
- All secrets loaded via environment variables (`.env` file, never committed)
- `.env.example` contains only placeholder values — required key names only
- Secrets in CI: use GitHub Actions Secrets (encrypted at rest)
- Production: use a secret manager (AWS Secrets Manager / GCP Secret Manager / HashiCorp Vault)
- `.gitignore` must include: `.env`, `.env.local`, `*.pem`, `*.key`

---

## 2. Token Encryption

Instagram access tokens are encrypted before storage:

```python
# app/utils/encryption.py
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

def encrypt_token(plaintext: str) -> str:
    key = bytes.fromhex(os.environ["TOKEN_ENCRYPTION_KEY"])  # 32-byte key
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return (nonce + ciphertext).hex()

def decrypt_token(encrypted_hex: str) -> str:
    key = bytes.fromhex(os.environ["TOKEN_ENCRYPTION_KEY"])
    data = bytes.fromhex(encrypted_hex)
    nonce, ciphertext = data[:12], data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None).decode()
```

- `TOKEN_ENCRYPTION_KEY`: 64-character hex string (32 bytes AES-256)
- Nonce is randomly generated per encryption, stored with ciphertext

---

## 3. OAuth Safety

- **CSRF state parameter**: signed JWT, validated on callback
- **State expiry**: 10 minutes maximum
- **Redirect URI**: registered in Meta app, validated server-side
- **Authorization code**: single-use, exchanged immediately
- **No token storage in browser**: only stored server-side, encrypted
- **Token not returned in API responses**: only scoped usage server-side

---

## 4. Upload Validation

All user file uploads are validated:

```python
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB

def validate_upload(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise ValidationError("Invalid file type")
    if file.size > MAX_FILE_SIZE_BYTES:
        raise ValidationError("File too large (max 20MB)")
    # Read first 512 bytes and verify magic bytes match declared MIME type
    header = await file.read(512)
    if not verify_magic_bytes(header, file.content_type):
        raise ValidationError("File content does not match declared type")
```

- Pre-signed S3 upload URLs include content-type restriction
- Server-side validation re-runs on `confirm-upload` step
- Optional: virus scanning adapter (ClamAV integration point)

---

## 5. Content Moderation

- AI-generated content passes through moderation check (see `docs/AI_PIPELINE.md`)
- User-uploaded images run through content classification before processing
- Moderation results stored in `GenerationJob.output_payload` and `AuditLog`
- Accounts with repeated violations: manual review flag (future feature)

---

## 6. Rate Limiting

```python
# Applied at API middleware level
RATE_LIMITS = {
    "POST /api/v1/reel-projects": "10/hour per user",
    "POST /api/v1/publish-jobs": "25/day per social_account (IG limit)",
    "POST /api/v1/auth/login": "10/minute per IP",
    "POST /api/v1/auth/register": "5/hour per IP",
    "default": "200/minute per user",
}
```

Implementation: `slowapi` (FastAPI rate limiting) with Redis backend.

---

## 7. Audit Logs

All sensitive actions are recorded in `audit_logs` table:

| Event                          | Logged?  |
|--------------------------------|----------|
| User login / logout            | ✅       |
| Social account connected       | ✅       |
| Social account disconnected    | ✅       |
| Reel project created           | ✅       |
| Reel approved                  | ✅       |
| Publish job started            | ✅       |
| Publish succeeded              | ✅       |
| Publish failed                 | ✅       |
| Token reconnect required       | ✅       |
| Moderation flag raised         | ✅       |

**Logging rules:**
- No passwords, tokens, or secrets in any log field
- No PII beyond user_id and workspace_id
- `ip_address` stored for auth events, never for content events
- Audit logs are **append-only** (no UPDATE or DELETE)

---

## 8. Abuse Prevention

- **Upload limit**: max 10 uploads/hour per user
- **Generation limit**: max 50 generations/day per workspace (configurable)
- **Account lockout**: 5 failed logins → 15-minute lockout
- **Content flag threshold**: 3 moderation flags → account flagged for review
- **API key rotation**: rotating `SECRET_KEY` invalidates all sessions
- **CORS**: strict allowlist of frontend origins
- **HTTPS only**: enforced in production via Nginx + Let's Encrypt
- **SQL injection**: prevented via SQLAlchemy ORM (parameterized queries only)
- **XSS**: Next.js escapes by default; dangerouslySetInnerHTML never used

---

## 9. Responsible Disclosure

See [SECURITY.md](../SECURITY.md) for the vulnerability reporting process.
