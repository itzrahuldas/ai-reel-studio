"""
Celery worker application entry point.
"""

import os
from celery import Celery

celery_app = Celery(
    "ai_reel_studio",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    include=[
        "app.tasks.generate_reel",
        "app.tasks.render_reel",
        "app.tasks.publish_reel",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # Only ack after task completes (safer)
    worker_prefetch_multiplier=1,  # One task at a time per worker slot
    task_routes={
        "app.tasks.generate_reel.*": {"queue": "generation"},
        "app.tasks.render_reel.*": {"queue": "rendering"},
        "app.tasks.publish_reel.*": {"queue": "publishing"},
    },
    task_default_queue="default",
    task_default_retry_delay=30,    # 30 seconds between retries
    task_max_retries=3,
)
