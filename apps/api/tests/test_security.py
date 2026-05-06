import os

os.environ["DEBUG"] = "false"
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-security-tests-1234567890")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "a" * 64)

from app.core.security import hash_password, verify_password


def test_hash_password_roundtrip_for_smoke_password() -> None:
    password = "StrongSmokePassword123!"

    hashed_password = hash_password(password)

    assert hashed_password
    assert hashed_password != password
    assert hashed_password.startswith("$2")
    assert verify_password(password, hashed_password) is True
