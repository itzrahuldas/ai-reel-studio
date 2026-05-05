"""
Application configuration — loaded from environment variables.
Uses pydantic-settings for type-safe config management.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────────────────────
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ── Security ───────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(..., min_length=32, description="JWT signing secret")
    TOKEN_ENCRYPTION_KEY: str = Field(..., min_length=64, description="AES-256 hex key for token encryption")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── CORS ───────────────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # ── Database ───────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_reel_studio",
        description="Async PostgreSQL connection string",
    )

    # ── Redis ──────────────────────────────────────────────────────────────
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string",
    )

    # ── Storage ────────────────────────────────────────────────────────────
    STORAGE_PROVIDER: Literal["s3", "local"] = "local"
    S3_ENDPOINT_URL: str | None = None
    S3_BUCKET: str = "ai-reel-studio"
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_REGION: str = "us-east-1"
    LOCAL_STORAGE_PATH: str = "/tmp/ai-reel-studio-storage"

    # ── AI Providers ───────────────────────────────────────────────────────
    AI_PROVIDER: Literal["openai", "gemini", "anthropic", "mock"] = "mock"
    AI_API_KEY: str | None = None
    AI_MODEL: str = "gpt-4.1-mini"
    IMAGE_ANALYSIS_PROVIDER: Literal["openai", "mock"] = "mock"
    IMAGE_ANALYSIS_MODEL: str = "gpt-4.1-mini"
    TTS_PROVIDER: Literal["elevenlabs", "openai", "google", "mock"] = "mock"
    TTS_MODEL: str = "gpt-4o-mini-tts"
    TTS_VOICE: str = "coral"
    AI_REQUEST_TIMEOUT_SECONDS: int = 60
    AI_MAX_RETRIES: int = 2
    AI_GENERATION_TEMPERATURE: float = 0.7
    AI_TIMEOUT_SECONDS: int = 60

    VIDEO_PROVIDER: Literal["runway", "luma", "stability", "none", "mock"] = "none"
    VIDEO_PROVIDER_API_KEY: str | None = None

    TTS_PROVIDER_API_KEY: str | None = None

    # ── Meta / Instagram ───────────────────────────────────────────────────
    META_APP_ID: str | None = None
    META_APP_SECRET: str | None = None
    META_REDIRECT_URI: str = "http://localhost:8000/api/v1/integrations/instagram/callback"
    META_GRAPH_API_VERSION: str = "v21.0"
    INSTAGRAM_INTEGRATION_MODE: Literal["live", "mock"] = "mock"

    # Stripe Billing
    STRIPE_MODE: Literal["mock", "live"] = "mock"
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_CREATOR_PRICE_ID: str | None = None
    STRIPE_PRO_PRICE_ID: str | None = None
    STRIPE_CUSTOMER_PORTAL_RETURN_URL: str | None = None
    STRIPE_CHECKOUT_SUCCESS_URL: str | None = None
    STRIPE_CHECKOUT_CANCEL_URL: str | None = None
    STRIPE_API_VERSION: str | None = None

    # ── Public URLs ────────────────────────────────────────────────────────
    API_PUBLIC_BASE_URL: str = "http://localhost:8000"
    STORAGE_PUBLIC_BASE_URL: str | None = None

    # ── Celery ─────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ── Generation Mode ────────────────────────────────────────────────────
    # 'async' = enqueue Celery task (requires Redis + worker running)
    # 'sync'  = run mock pipeline inline in API (no Redis needed for dev)
    GENERATION_MODE: str = "async"
    RENDER_MODE: str = "async"
    PUBLISH_MODE: str = "async"

    # ── File Upload ────────────────────────────────────────────────────────
    MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024  # 20 MB default

    # ── Rate Limiting ──────────────────────────────────────────────────────
    RATE_LIMIT_GENERATION_PER_HOUR: int = 10
    RATE_LIMIT_PUBLISH_PER_DAY: int = 25

    # ── Logging ────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "console"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — call this everywhere."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
