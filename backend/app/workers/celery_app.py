"""
Celery application configuration.
Handles background task execution for email sending, enrichment, analytics, etc.
"""

from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "apex_outreach",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Route tasks to specific queues
    task_routes={
        "app.workers.email_tasks.*": {"queue": "email"},
        "app.workers.linkedin_tasks.*": {"queue": "linkedin"},
        "app.workers.whatsapp_tasks.*": {"queue": "whatsapp"},
        "app.workers.social_tasks.*": {"queue": "social"},
        "app.workers.ai_tasks.*": {"queue": "ai"},
        "app.workers.enrichment_tasks.*": {"queue": "enrichment"},
        "app.workers.analytics_tasks.*": {"queue": "analytics"},
    },
    # Periodic task schedule (Celery Beat)
    beat_schedule={
        "check-email-replies": {
            "task": "app.workers.email_tasks.check_replies",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
        },
        "process-scheduled-sends": {
            "task": "app.workers.email_tasks.process_scheduled_sends",
            "schedule": crontab(minute="*/2"),  # Every 2 minutes
        },
        "daily-metrics-rollup": {
            "task": "app.workers.analytics_tasks.daily_rollup",
            "schedule": crontab(hour=23, minute=55),  # 11:55 PM IST
        },
        "advance-sequences": {
            "task": "app.workers.email_tasks.advance_sequences",
            "schedule": crontab(minute="*/10"),  # Every 10 minutes
        },
        # LinkedIn queue (slower cadence due to tight limits)
        "process-linkedin-queue": {
            "task": "app.workers.linkedin_tasks.process_linkedin_queue",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
        },
        # WhatsApp queue
        "process-whatsapp-queue": {
            "task": "app.workers.whatsapp_tasks.process_whatsapp_queue",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
        },
        # Instagram queue
        "process-instagram-queue": {
            "task": "app.workers.social_tasks.process_instagram_queue",
            "schedule": crontab(minute="*/10"),  # Every 10 minutes
        },
    },
)

# Auto-discover tasks in workers package
celery_app.autodiscover_tasks(["app.workers"])
