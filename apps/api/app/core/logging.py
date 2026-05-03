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
    {"token", "access_token", "refresh_token", "password", "secret", "key", "authorization"}
)


def redact_sensitive_fields(logger: object, method: str, event_dict: EventDict) -> EventDict:
    """Structlog processor that redacts known sensitive field names."""
    for key in list(event_dict.keys()):
        if key.lower() in REDACTED_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging(log_level: str = "INFO", log_format: str = "console") -> None:
    """Configure structlog for the application."""
    shared_processors: list = [
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

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Redirect stdlib logging to structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(log_level.upper()),
    )
