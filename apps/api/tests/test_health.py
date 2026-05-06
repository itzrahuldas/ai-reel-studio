import json
import os
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

os.environ["DEBUG"] = "false"
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-health-checks")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "a" * 64)

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)


def test_root_health_liveness_shape():
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "api"
    assert payload["environment"] in {"development", "test", "staging", "production"}
    assert payload["version"]


def test_readiness_returns_ready_with_mocked_dependencies():
    ok = {"status": "ok"}
    with (
        patch("app.api.v1.routers.health._check_database", new=AsyncMock(return_value=ok)),
        patch("app.api.v1.routers.health._check_redis", new=AsyncMock(return_value=ok)),
        patch("app.api.v1.routers.health._check_celery_broker", new=AsyncMock(return_value=ok)),
        patch("app.api.v1.routers.health._check_storage", new=AsyncMock(return_value=ok)),
        patch("app.api.v1.routers.health._check_config", new=AsyncMock(return_value=ok)),
    ):
        response = client.get("/api/v1/health/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["service"] == "api"
    assert set(payload["checks"]) == {
        "database",
        "redis",
        "celery_broker",
        "storage",
        "config",
    }


def test_safe_config_does_not_expose_secrets(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_should_not_leak")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_should_not_leak")
    monkeypatch.setattr(settings, "AI_API_KEY", "ai_key_should_not_leak")

    response = client.get("/api/v1/health/config")

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload)
    assert "sk_test_should_not_leak" not in serialized
    assert "whsec_should_not_leak" not in serialized
    assert "ai_key_should_not_leak" not in serialized
    assert payload["service"] == "api"
    assert "api_public_base_url_configured" in payload
    assert "frontend_url_configured" in payload
