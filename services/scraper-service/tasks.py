"""
Celery tasks for the scraper-service.
Orchestrates Scrapy spiders and Selenium scrapers.
"""
import logging
import os
from datetime import datetime, timezone

import MySQLdb
from celery import chain, group
from celery_app import app

logger = logging.getLogger(__name__)


def _get_db():
    return MySQLdb.connect(
        host=os.environ.get("DB_HOST", "mysql"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "nexus"),
        passwd=os.environ.get("DB_PASSWORD", "nexus_secret"),
        db=os.environ.get("DB_NAME", "nexus_core"),
        charset="utf8mb4",
    )


def _get_company(company_id: int) -> dict | None:
    db = _get_db()
    try:
        cur = db.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM companies_company WHERE id = %s", (company_id,))
        return cur.fetchone()
    finally:
        db.close()


def _save_data_point(company_id: int, source_type: str, source_url: str,
                     raw_text: str, structured_json: dict | None,
                     confidence_score: float = 1.0) -> int:
    db = _get_db()
    try:
        cur = db.cursor()
        import json
        cur.execute(
            """INSERT INTO companies_datapoint
               (company_id, source_type, source_url, raw_text, structured_json, extracted_at, confidence_score)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                company_id, source_type, source_url, raw_text,
                json.dumps(structured_json) if structured_json else None,
                datetime.now(timezone.utc),
                confidence_score,
            ),
        )
        db.commit()
        return cur.lastrowid
    finally:
        db.close()


def _update_company_crawled(company_id: int) -> None:
    db = _get_db()
    try:
        cur = db.cursor()
        cur.execute(
            "UPDATE companies_company SET last_crawled_at = %s WHERE id = %s",
            (datetime.now(timezone.utc), company_id),
        )
        db.commit()
    finally:
        db.close()


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_company_scrape(self, company_id: int):
    """
    Orchestrate all scrapers for a company.
    Runs Scrapy spiders (news, jobs, crunchbase) and Selenium scrapers (linkedin)
    in parallel via Celery group, then aggregates results.
    """
    company = _get_company(company_id)
    if not company:
        logger.error("Company %s not found", company_id)
        return {"status": "error", "reason": "company_not_found"}

    logger.info("Starting scrape for company %s (%s)", company_id, company["name"])

    try:
        scrape_group = group(
            run_scrapy_spider.s("news", company_id),
            run_scrapy_spider.s("jobs", company_id),
            run_scrapy_spider.s("crunchbase", company_id),
            run_selenium_scraper.s("linkedin_company", company_id),
        )
        result = (scrape_group | aggregate_scrape_results.s(company_id)).delay()
        return {"status": "dispatched", "company_id": company_id, "chord_id": result.id}

    except Exception as exc:
        logger.error("Scrape dispatch failed for company %s: %s", company_id, exc)
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_scrapy_spider(self, spider_name: str, company_id: int) -> dict:
    """Run a named Scrapy spider for a company using CrawlerRunner."""
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings

    company = _get_company(company_id)
    if not company:
        return {"status": "error", "spider": spider_name, "count": 0}

    spider_map = {
        "news": "news_spider",
        "jobs": "jobs_spider",
        "crunchbase": "crunchbase_spider",
    }
    spider_cls_name = spider_map.get(spider_name)
    if not spider_cls_name:
        return {"status": "error", "reason": f"Unknown spider: {spider_name}"}

    try:
        import sys
        sys.path.insert(0, "/app")
        settings = get_project_settings()
        settings.setmodule("scrapy_project.settings")

        process = CrawlerProcess(settings)

        from scrapy_project.spiders import news_spider, jobs_spider, crunchbase_spider
        spider_classes = {
            "news_spider": news_spider.NewsSpider,
            "jobs_spider": jobs_spider.JobsSpider,
            "crunchbase_spider": crunchbase_spider.CrunchbaseSpider,
        }
        process.crawl(spider_classes[spider_cls_name], company_id=company_id, company=company)
        process.start()
        logger.info("Spider %s completed for company %s", spider_name, company_id)
        return {"status": "ok", "spider": spider_name, "company_id": company_id}

    except Exception as exc:
        logger.error("Spider %s failed for company %s: %s", spider_name, company_id, exc)
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=2, default_retry_delay=60)
def run_selenium_scraper(self, scraper_name: str, company_id: int) -> dict:
    """Run a named Selenium scraper for a company."""
    company = _get_company(company_id)
    if not company:
        return {"status": "error", "scraper": scraper_name, "count": 0}

    try:
        if scraper_name == "linkedin_company":
            from selenium_scrapers.linkedin_company import LinkedInCompanyScraper
            scraper = LinkedInCompanyScraper(company_id=company_id, company=company)
            results = scraper.scrape()
            for r in results:
                _save_data_point(
                    company_id=company_id,
                    source_type="linkedin",
                    source_url=r.get("url", ""),
                    raw_text=r.get("raw_text", ""),
                    structured_json=r.get("structured", {}),
                )
            return {"status": "ok", "scraper": scraper_name, "count": len(results)}
        else:
            return {"status": "error", "reason": f"Unknown scraper: {scraper_name}"}

    except Exception as exc:
        logger.error("Selenium scraper %s failed for company %s: %s", scraper_name, company_id, exc)
        raise self.retry(exc=exc)


@app.task
def aggregate_scrape_results(results: list, company_id: int) -> dict:
    """Called after all scrape tasks complete. Updates last_crawled_at."""
    logger.info("Aggregating scrape results for company %s: %s", company_id, results)
    _update_company_crawled(company_id)
    total = sum(r.get("count", 0) for r in results if isinstance(r, dict))
    return {
        "company_id": company_id,
        "total_data_points": total,
        "tasks": results,
    }
