"""
Celery client configuration for the API.
Used ONLY for enqueueing tasks — not for running them.
The actual task execution happens in apps/worker/.
"""

from celery import Celery

from app.core.config import settings

# Minimal Celery app — client only, no task registration
celery_client = Celery(
    "ai_reel_studio_client",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_client.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
