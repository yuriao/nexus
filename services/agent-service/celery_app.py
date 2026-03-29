import os
from celery import Celery

os.environ.setdefault("CELERY_BROKER_URL", "redis://redis:6379/1")

app = Celery(
    "agent",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/1"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/2"),
    include=["tasks"],
)
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    broker_connection_retry_on_startup=True,
    task_routes={"tasks.run_agent_analysis": {"queue": "agent"}},
)
