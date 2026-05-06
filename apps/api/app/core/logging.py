"""
Structured logging configuration using structlog.
All log lines include correlation_id for request tracing.
Sensitive fields are automatically redacted.
"""

import logging
import sys

import structlog
from structlog.typing import EventDict

REDACTED_KEYS = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "password",
        "secret",
        "key",
        "api_key",
        "authorization",
        "stripe_secret_key",
        "stripe_webhook_secret",
        "meta_app_secret",
        "meta_access_token",
        "openai_api_key",
        "ai_api_key",
    }
)
REDACTED_KEY_FRAGMENTS = frozenset(
    {"password", "token", "secret", "api_key", "authorization"}
)


def redact_sensitive_fields(_logger: object, _method: str, event_dict: EventDict) -> EventDict:
    """Structlog processor that redacts known sensitive field names."""
    for key in list(event_dict.keys()):
        normalized_key = key.lower().replace("-", "_")
        if normalized_key in REDACTED_KEYS or any(
            fragment in normalized_key for fragment in REDACTED_KEY_FRAGMENTS
        ):
            event_dict[key] = "[REDACTED]"
    return event_dict


def _log_level_value(log_level: str) -> int:
    """Return a valid stdlib logging level, defaulting to INFO for unknown values."""
    level = logging.getLevelName(log_level.upper())
    return level if isinstance(level, int) else logging.INFO


def configure_logging(log_level: str = "INFO", log_format: str = "console") -> None:
    """Configure structlog for the application."""
    level = _log_level_value(log_level)
    shared_processors: list[object] = [
        structlog.stdlib.filter_by_level,
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        redact_sensitive_fields,
    ]

    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
        force=True,
    )

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
