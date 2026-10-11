from celery import Celery

from homelab_pulse.config import get_settings

settings = get_settings()
celery_app = Celery(
    "homelab_pulse",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["homelab_pulse.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "monitor-enabled-services": {
            "task": "homelab_pulse.monitor_enabled_services",
            "schedule": float(settings.monitor_interval_seconds),
        }
    },
)

