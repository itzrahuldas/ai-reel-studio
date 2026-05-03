"""
Security utilities: JWT creation/validation, password hashing.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

logger = structlog.get_logger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str | UUID, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str | UUID) -> str:
    """Create a signed JWT refresh token."""
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.
    Raises JWTError if invalid or expired.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


def create_oauth_state_token(workspace_id: str, user_id: str) -> str:
    """Create a short-lived CSRF state token for OAuth flows."""
    expire = datetime.now(UTC) + timedelta(minutes=10)
    payload = {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "exp": expire,
        "type": "oauth_state",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def validate_oauth_state_token(state: str) -> dict[str, Any]:
    """
    Validate the OAuth state token.
    Raises JWTError if invalid, expired, or wrong type.
    """
    payload = jwt.decode(state, settings.SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != "oauth_state":
        raise JWTError("Invalid state token type")
    return payload


# ── Token Encryption ──────────────────────────────────────────────────────────

def _get_fernet() -> Fernet:
    """Initialize Fernet with TOKEN_ENCRYPTION_KEY."""
    if not settings.TOKEN_ENCRYPTION_KEY:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not set.")
    # Fernet requires a 32-byte url-safe base64-encoded key
    # If the key provided is just 32 characters or not base64 encoded,
    # we can pad/encode it, but let's assume it's correctly formatted
    # or we can derive a safe key from it.
    import base64
    key = settings.TOKEN_ENCRYPTION_KEY.encode('utf-8')
    if len(key) < 32:
        key = key.ljust(32, b'0')
    if len(key) > 32 and len(key) != 44:
        key = key[:32]

    # Ensure it's urlsafe_b64encoded if it isn't already
    try:
        Fernet(key)
        final_key = key
    except (ValueError, TypeError):
        final_key = base64.urlsafe_b64encode(key[:32])

    return Fernet(final_key)


def encrypt_token(token: str) -> str:
    """Encrypt a raw token before storing in database."""
    f = _get_fernet()
    return f.encrypt(token.encode('utf-8')).decode('utf-8')


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a token retrieved from the database."""
    f = _get_fernet()
    return f.decrypt(encrypted_token.encode('utf-8')).decode('utf-8')
