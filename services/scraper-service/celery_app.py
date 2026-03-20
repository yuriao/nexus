import os
from celery import Celery

os.environ.setdefault("CELERY_BROKER_URL", "redis://redis:6379/1")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://redis:6379/2")

app = Celery("scraper")
app.config_from_object("celeryconfig", silent=True)
app.conf.update(
    broker_url=os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/1"),
    result_backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/2"),
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_routes={
        "tasks.run_company_scrape": {"queue": "scraper"},
        "tasks.run_scrapy_spider": {"queue": "scraper"},
        "tasks.run_selenium_scraper": {"queue": "scraper"},
        "tasks.aggregate_scrape_results": {"queue": "scraper"},
    },
)
app.autodiscover_tasks(["tasks"])
