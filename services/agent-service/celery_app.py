import os
import sys

sys.path.insert(0, "/app")

from celery import Celery
from celery.schedules import crontab

app = Celery(
    "agent",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/1"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/2"),
    include=["tasks", "beat_tasks"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    broker_connection_retry_on_startup=True,
    task_routes={
        "tasks.run_agent_analysis": {"queue": "agent"},
        "tasks.schedule_due_companies": {"queue": "beat"},
        "tasks.enrich_all_companies": {"queue": "beat"},
        "tasks.enrich_company": {"queue": "beat"},
    },
    beat_schedule={
        "hourly-scrape-and-report": {
            "task": "tasks.schedule_due_companies",
            "schedule": crontab(minute="0"),
            "options": {"queue": "beat"},
        },
        "enrich-companies": {
            "task": "tasks.enrich_all_companies",
            "schedule": crontab(minute="30", hour="*/6"),
            "options": {"queue": "beat"},
        },
    },
)
