import os
from celery import Celery

app = Celery(
    "scraper",
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
    task_routes={
        "tasks.run_company_scrape": {"queue": "scraper"},
        "tasks.run_scrapy_spider": {"queue": "scraper"},
        "tasks.run_selenium_scraper": {"queue": "scraper"},
        "tasks.aggregate_scrape_results": {"queue": "scraper"},
    },
)
