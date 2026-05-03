"""
Custom FastAPI middleware.
- CorrelationIDMiddleware: attaches a unique request_id to every request
- RateLimitMiddleware: wraps slowapi for rate limiting
"""

import uuid
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)

CORRELATION_ID_HEADER = "X-Request-ID"


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Attaches a correlation ID to every request.
    Uses X-Request-ID header if provided by caller, otherwise generates a UUID.
    Adds the ID to structlog context so all log lines in a request include it.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        # Bind to structlog context for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=correlation_id)

        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Placeholder for rate limiting middleware.
    In production, configure slowapi on the FastAPI app instance.
    See: https://slowapi.readthedocs.io/
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        return await call_next(request)
