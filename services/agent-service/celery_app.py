import os
from celery import Celery

os.environ.setdefault("CELERY_BROKER_URL", "redis://redis:6379/1")

app = Celery("agent")
app.conf.update(
    broker_url=os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/1"),
    result_backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/2"),
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_routes={
        "tasks.run_agent_analysis": {"queue": "agent"},
    },
)
app.autodiscover_tasks(["tasks"])
