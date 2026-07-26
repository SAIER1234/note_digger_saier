"""Celery application configuration."""

import os
from celery import Celery

from app.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, DEV_MODE

celery_app = Celery(
    "note_digger",
    broker=CELERY_BROKER_URL if not DEV_MODE else "memory://",
    backend=CELERY_RESULT_BACKEND if not DEV_MODE else "cache+memory://",
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=600,
    task_time_limit=900,
    result_expires=86400,
)

# Task discovery: import the task module to register tasks.
# Must be at bottom to avoid circular import (transcription.py imports celery_app).
def _register_tasks():
    import app.tasks.transcription  # noqa: F401 — registers @celery_app.task

_register_tasks()
