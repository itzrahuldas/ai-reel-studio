"""Operational health endpoints for deployment smoke checks."""

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import settings

router = APIRouter()

CheckResult = dict[str, Any]


def _is_configured(value: str | None) -> bool:
    if value is None:
        return False
    stripped = value.strip()
    return bool(stripped) and not stripped.startswith("<")


def _uses_async_workers() -> bool:
    return any(
        getattr(settings, setting_name, "async") == "async"
        for setting_name in ("GENERATION_MODE", "RENDER_MODE", "PUBLISH_MODE")
    )


def _check_ok(**extra: Any) -> CheckResult:
    return {"status": "ok", **extra}


def _check_failed(message: str, *, required: bool = True, **extra: Any) -> CheckResult:
    return {"status": "failed", "message": message, "required": required, **extra}


def _check_degraded(message: str, *, required: bool = True, **extra: Any) -> CheckResult:
    return {"status": "degraded", "message": message, "required": required, **extra}


def _check_skipped(message: str, *, required: bool = False, **extra: Any) -> CheckResult:
    return {"status": "skipped", "message": message, "required": required, **extra}


async def _check_database(db: DbSession) -> CheckResult:
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        return _check_failed("Database connectivity check failed.", error_type=type(exc).__name__)
    return _check_ok()


async def _ping_redis_url(url: str, *, label: str, required: bool) -> CheckResult:
    client = Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
    try:
        await client.ping()
    except RedisError as exc:
        return _check_failed(
            f"{label} connectivity check failed.",
            required=required,
            error_type=type(exc).__name__,
        )
    finally:
        await client.aclose()
    return _check_ok(required=required)


async def _check_redis() -> CheckResult:
    if not _is_configured(settings.REDIS_URL):
        return _check_skipped("REDIS_URL is not configured.", required=_uses_async_workers())
    return await _ping_redis_url(
        settings.REDIS_URL,
        label="Redis",
        required=_uses_async_workers(),
    )


async def _check_celery_broker() -> CheckResult:
    if not _uses_async_workers():
        return _check_skipped("All runtime modes are sync; Celery broker is optional.")
    if not _is_configured(settings.CELERY_BROKER_URL):
        return _check_failed("CELERY_BROKER_URL is required for async runtime modes.")
    if not settings.CELERY_BROKER_URL.startswith(("redis://", "rediss://")):
        return _check_degraded(
            "Celery broker reachability is only implemented for Redis URLs.",
            broker_type=settings.CELERY_BROKER_URL.split(":", 1)[0],
        )
    return await _ping_redis_url(
        settings.CELERY_BROKER_URL,
        label="Celery broker",
        required=True,
    )


async def _check_storage() -> CheckResult:
    if settings.STORAGE_PROVIDER == "local":
        storage_path = Path(settings.LOCAL_STORAGE_PATH)
        probe_path = storage_path / f".healthcheck-{uuid4().hex}"
        try:
            storage_path.mkdir(parents=True, exist_ok=True)
            probe_path.write_text("ok", encoding="utf-8")
            probe_path.unlink(missing_ok=True)
        except OSError as exc:
            return _check_failed(
                "Local storage directory is not writable.",
                error_type=type(exc).__name__,
            )
        return _check_ok(provider="local")

    missing: list[str] = []
    if not _is_configured(settings.S3_BUCKET):
        missing.append("S3_BUCKET")
    if settings.APP_ENV in {"staging", "production"} and not _is_configured(
        settings.STORAGE_PUBLIC_BASE_URL
    ):
        missing.append("STORAGE_PUBLIC_BASE_URL")
    if missing:
        return _check_failed("Object storage configuration is incomplete.", missing=missing)
    return _check_ok(provider=settings.STORAGE_PROVIDER)


def _config_warnings() -> list[str]:
    warnings: list[str] = []
    if settings.APP_ENV in {"staging", "production"}:
        for name in ("FRONTEND_URL", "API_PUBLIC_BASE_URL", "STORAGE_PUBLIC_BASE_URL"):
            value = getattr(settings, name, None)
            if isinstance(value, str) and ("localhost" in value or "127.0.0.1" in value):
                warnings.append(f"{name} points at localhost in {settings.APP_ENV}.")
    return warnings


async def _check_config() -> CheckResult:
    missing: list[str] = []
    for name in ("SECRET_KEY", "TOKEN_ENCRYPTION_KEY"):
        if not _is_configured(getattr(settings, name, None)):
            missing.append(name)

    if settings.APP_ENV in {"staging", "production"}:
        for name in ("FRONTEND_URL", "API_PUBLIC_BASE_URL"):
            if not _is_configured(getattr(settings, name, None)):
                missing.append(name)

    if settings.STRIPE_MODE == "live":
        for name in (
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "STRIPE_CREATOR_PRICE_ID",
            "STRIPE_PRO_PRICE_ID",
        ):
            if not _is_configured(getattr(settings, name, None)):
                missing.append(name)

    if settings.INSTAGRAM_INTEGRATION_MODE == "live":
        for name in ("META_APP_ID", "META_APP_SECRET", "META_REDIRECT_URI"):
            if not _is_configured(getattr(settings, name, None)):
                missing.append(name)

    if "openai" in {
        settings.AI_PROVIDER,
        settings.IMAGE_ANALYSIS_PROVIDER,
        settings.TTS_PROVIDER,
    } and not _is_configured(settings.AI_API_KEY):
        missing.append("AI_API_KEY")

    if missing:
        return _check_failed("Required configuration is missing.", missing=sorted(set(missing)))

    warnings = _config_warnings()
    if warnings:
        return _check_degraded("Configuration has staging/production warnings.", warnings=warnings)
    return _check_ok()


def _overall_status(checks: dict[str, CheckResult]) -> str:
    if any(
        check["status"] == "failed" and check.get("required", True)
        for check in checks.values()
    ):
        return "not_ready"
    if any(check["status"] in {"failed", "degraded"} for check in checks.values()):
        return "degraded"
    return "ready"


@router.get("/readiness")
async def readiness(db: DbSession) -> dict[str, Any]:
    """Return deploy-time readiness across core dependencies."""
    checks = {
        "database": await _check_database(db),
        "redis": await _check_redis(),
        "celery_broker": await _check_celery_broker(),
        "storage": await _check_storage(),
        "config": await _check_config(),
    }
    return {
        "status": _overall_status(checks),
        "service": "api",
        "environment": settings.APP_ENV,
        "version": settings.APP_VERSION,
        "checks": checks,
    }


@router.get("/config")
async def safe_config() -> dict[str, Any]:
    """Return a safe deployment config summary without secret values."""
    return {
        "service": "api",
        "environment": settings.APP_ENV,
        "version": settings.APP_VERSION,
        "generation_mode": settings.GENERATION_MODE,
        "render_mode": settings.RENDER_MODE,
        "publish_mode": settings.PUBLISH_MODE,
        "stripe_mode": settings.STRIPE_MODE,
        "instagram_mode": settings.INSTAGRAM_INTEGRATION_MODE,
        "ai_provider": settings.AI_PROVIDER,
        "image_analysis_provider": settings.IMAGE_ANALYSIS_PROVIDER,
        "tts_provider": settings.TTS_PROVIDER,
        "storage_provider": settings.STORAGE_PROVIDER,
        "api_public_base_url_configured": _is_configured(settings.API_PUBLIC_BASE_URL),
        "frontend_url_configured": _is_configured(settings.FRONTEND_URL),
        "storage_public_base_url_configured": _is_configured(settings.STORAGE_PUBLIC_BASE_URL),
    }
