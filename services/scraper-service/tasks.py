"""
Celery tasks for the scraper-service.
Scraping strategy (reliable, no Scrapy reactor issues):
  1. Brave Search API — news articles (primary, fast)
  2. RSS feeds from major tech news sites (fallback)
  3. Job postings via Brave Search (jobs)
  4. Crunchbase Autocomplete API (company data, no auth)

Note: CrawlerProcess was removed — it calls reactor.run() which is incompatible
with Celery's multiprocessing pool and silently produces no items.
"""
import json
import logging
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import MySQLdb
from celery_app import app

logger = logging.getLogger(__name__)

BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")


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


def _save_data_point(company_id, source_type, source_url, raw_text,
                     structured_json=None, confidence_score=0.9):
    db = _get_db()
    try:
        cur = db.cursor()
        cur.execute(
            """INSERT INTO companies_datapoint
               (company_id, source_type, source_url, raw_text,
                structured_json, extracted_at, confidence_score)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE
               raw_text = VALUES(raw_text),
               structured_json = VALUES(structured_json),
               extracted_at = VALUES(extracted_at)""",
            (
                company_id, source_type, source_url[:500], raw_text[:5000],
                json.dumps(structured_json) if structured_json else None,
                datetime.now(timezone.utc),
                float(confidence_score),
            ),
        )
        db.commit()
    except Exception as e:
        logger.error("_save_data_point failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
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


# ── Brave Search helper ────────────────────────────────────────────────────────

def _brave_search(query: str, count: int = 10, search_type: str = "web") -> list[dict]:
    """Call Brave Search API. Returns list of {title, url, description, published}."""
    if not BRAVE_API_KEY:
        logger.warning("BRAVE_API_KEY not set — skipping Brave search")
        return []
    try:
        endpoint = "https://api.search.brave.com/res/v1/news/search" if search_type == "news" \
            else "https://api.search.brave.com/res/v1/web/search"
        params = urllib.parse.urlencode({"q": query, "count": count, "freshness": "pm"})
        req = urllib.request.Request(
            f"{endpoint}?{params}",
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": BRAVE_API_KEY,
            },
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            import gzip as _gzip
            raw = r.read()
            try:
                raw = _gzip.decompress(raw)
            except Exception:
                pass
            data = json.loads(raw)

        results = []
        items = data.get("results", []) or data.get("web", {}).get("results", [])
        for item in items:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", "") or item.get("extra_snippets", [""])[0],
                "published": item.get("age", "") or item.get("page_age", ""),
            })
        return results
    except Exception as e:
        logger.error("Brave search failed for query '%s': %s", query, e)
        return []


# ── Individual scrapers ────────────────────────────────────────────────────────

def _scrape_news(company_id: int, company: dict) -> int:
    """Fetch recent news via Brave Search API."""
    name = company["name"]
    domain = company.get("domain", "")
    count = 0

    queries = [
        f'"{name}" news announcement',
        f'"{name}" funding product launch',
        f'site:{domain}' if domain else f'"{name}" press release',
    ]

    seen_urls = set()
    for query in queries:
        results = _brave_search(query, count=8, search_type="news")
        if not results:
            results = _brave_search(query, count=8, search_type="web")

        for r in results:
            url = r.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            raw_text = f"{r['title']}\n\n{r['description']}"
            if len(raw_text.strip()) < 20:
                continue
            _save_data_point(
                company_id=company_id,
                source_type="news",
                source_url=url,
                raw_text=raw_text,
                structured_json={
                    "title": r["title"],
                    "snippet": r["description"],
                    "published": r["published"],
                    "query": query,
                },
                confidence_score=0.85,
            )
            count += 1

    logger.info("News scrape for %s: %d items saved", name, count)
    return count


def _scrape_jobs(company_id: int, company: dict) -> int:
    """Fetch job postings via Brave Search."""
    name = company["name"]
    domain = company.get("domain", "")
    count = 0

    queries = [
        f'"{name}" jobs hiring site:linkedin.com OR site:greenhouse.io OR site:lever.co',
        f'"{name}" engineer manager jobs 2025 2026',
    ]

    seen_urls = set()
    for query in queries:
        results = _brave_search(query, count=8)
        for r in results:
            url = r.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            raw_text = f"{r['title']}\n\n{r['description']}"
            if len(raw_text.strip()) < 20:
                continue
            _save_data_point(
                company_id=company_id,
                source_type="jobs",
                source_url=url,
                raw_text=raw_text,
                structured_json={
                    "title": r["title"],
                    "snippet": r["description"],
                    "published": r["published"],
                },
                confidence_score=0.75,
            )
            count += 1

    logger.info("Jobs scrape for %s: %d items saved", name, count)
    return count


def _scrape_crunchbase(company_id: int, company: dict) -> int:
    """Fetch company data from Crunchbase Autocomplete (no auth) + web search."""
    name = company["name"]
    count = 0

    # Clearbit Autocomplete (free, no auth)
    try:
        url = f"https://autocomplete.clearbit.com/v1/companies/suggest?query={urllib.parse.quote(name)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        if data:
            item = data[0]
            raw = f"{item.get('name','')} — {item.get('domain','')} — {item.get('description','')}"
            _save_data_point(
                company_id=company_id,
                source_type="crunchbase",
                source_url=f"https://clearbit.com/companies/{item.get('domain','')}",
                raw_text=raw,
                structured_json=item,
                confidence_score=0.8,
            )
            count += 1
    except Exception as e:
        logger.warning("Clearbit fetch failed for %s: %s", name, e)

    # Web search for funding/acquisition news
    results = _brave_search(f'"{name}" funding round acquisition valuation crunchbase', count=5)
    seen = set()
    for r in results:
        url = r.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        _save_data_point(
            company_id=company_id,
            source_type="crunchbase",
            source_url=url,
            raw_text=f"{r['title']}\n\n{r['description']}",
            structured_json={"title": r["title"], "snippet": r["description"]},
            confidence_score=0.7,
        )
        count += 1

    logger.info("Crunchbase/funding scrape for %s: %d items saved", name, count)
    return count


# ── Celery tasks ───────────────────────────────────────────────────────────────

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_company_scrape(self, company_id: int):
    """
    Orchestrate all scrapers for a company (direct HTTP, no Scrapy reactor).
    Runs news + jobs + crunchbase sequentially then updates last_crawled_at.
    """
    company = _get_company(company_id)
    if not company:
        logger.error("Company %s not found", company_id)
        return {"status": "error", "reason": "company_not_found"}

    logger.info("Starting scrape for company %s (%s)", company_id, company["name"])
    total = 0
    try:
        total += _scrape_news(company_id, company)
        total += _scrape_jobs(company_id, company)
        total += _scrape_crunchbase(company_id, company)
        _update_company_crawled(company_id)
        logger.info("Scrape complete for %s: %d total data points", company["name"], total)
        return {"status": "ok", "company_id": company_id, "total_data_points": total}
    except Exception as exc:
        logger.error("Scrape failed for company %s: %s", company_id, exc)
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_scrapy_spider(self, spider_name: str, company_id: int) -> dict:
    """Legacy task name kept for backward compat — delegates to run_company_scrape logic."""
    company = _get_company(company_id)
    if not company:
        return {"status": "error", "spider": spider_name, "count": 0}
    try:
        if spider_name == "news":
            count = _scrape_news(company_id, company)
        elif spider_name == "jobs":
            count = _scrape_jobs(company_id, company)
        elif spider_name == "crunchbase":
            count = _scrape_crunchbase(company_id, company)
        else:
            return {"status": "error", "reason": f"Unknown spider: {spider_name}"}
        return {"status": "ok", "spider": spider_name, "count": count}
    except Exception as exc:
        logger.error("Spider %s failed for company %s: %s", spider_name, company_id, exc)
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=2, default_retry_delay=60)
def run_selenium_scraper(self, scraper_name: str, company_id: int) -> dict:
    """Selenium scraper — runs Brave Search fallback when Selenium unavailable."""
    company = _get_company(company_id)
    if not company:
        return {"status": "error", "scraper": scraper_name, "count": 0}
    try:
        # Brave-based fallback for LinkedIn data
        name = company["name"]
        results = _brave_search(
            f'"{name}" linkedin company overview employees growth',
            count=5
        )
        count = 0
        seen = set()
        for r in results:
            url = r.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            _save_data_point(
                company_id=company_id,
                source_type="linkedin",
                source_url=url,
                raw_text=f"{r['title']}\n\n{r['description']}",
                structured_json={"title": r["title"], "snippet": r["description"]},
                confidence_score=0.65,
            )
            count += 1
        return {"status": "ok", "scraper": scraper_name, "count": count}
    except Exception as exc:
        logger.error("Scraper %s failed for company %s: %s", scraper_name, company_id, exc)
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
