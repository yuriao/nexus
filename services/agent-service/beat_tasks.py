"""
Beat tasks — scheduled work that drives automatic scraping, reporting, and company enrichment.
These run in the `beat` queue, consumed by the celery-beat-worker service.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import MySQLdb

from celery import current_app
from celery import chain

logger = logging.getLogger(__name__)


def _get_db():
    return MySQLdb.connect(
        host=os.environ.get("DB_HOST", "mysql"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER", "nexus"),
        passwd=os.environ.get("DB_PASSWORD", "nexus_secret"),
        db=os.environ.get("DB_NAME", "nexus_core"),
        charset="utf8mb4",
        connect_timeout=10,
    )


# ─── Scheduler ────────────────────────────────────────────────────────────────

@current_app.task(name="tasks.schedule_due_companies", bind=True, max_retries=2)
def schedule_due_companies(self):
    """
    Hourly: find all companies where last_crawled_at < now - crawl_frequency_hours
    and dispatch scrape → report chain for each.
    """
    db = _get_db()
    try:
        cur = db.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("""
            SELECT id, name, crawl_frequency_hours, last_crawled_at
            FROM companies_company
            WHERE last_crawled_at IS NULL
               OR last_crawled_at < DATE_SUB(NOW(), INTERVAL crawl_frequency_hours HOUR)
            ORDER BY last_crawled_at ASC
            LIMIT 20
        """)
        due = cur.fetchall()
    finally:
        db.close()

    if not due:
        logger.info("No companies due for scraping")
        return {"dispatched": 0}

    dispatched = 0
    for company in due:
        company_id = company["id"]
        company_name = company["name"]
        try:
            _dispatch_scrape_and_report(company_id)
            dispatched += 1
            logger.info("Dispatched scrape+report for %s (id=%s)", company_name, company_id)
        except Exception as e:
            logger.error("Failed to dispatch for %s: %s", company_name, e)

    return {"dispatched": dispatched, "total_due": len(due)}


def _dispatch_scrape_and_report(company_id: int):
    """Create a report record and dispatch scrape → agent chain."""
    db = _get_db()
    try:
        cur = db.cursor(MySQLdb.cursors.DictCursor)

        # Get latest version
        cur.execute(
            "SELECT MAX(version) as max_v FROM reports_researchreport WHERE company_id = %s",
            (company_id,)
        )
        row = cur.fetchone()
        version = (row["max_v"] or 0) + 1

        # Create report record
        report_id = str(uuid.uuid4())
        rid = report_id.replace("-", "")
        cur.execute(
            """INSERT INTO reports_researchreport
               (id, company_id, version, status, requested_by_user_id, created_at, updated_at)
               VALUES (%s, %s, %s, 'pending', 0, NOW(), NOW())""",
            (rid, company_id, version)
        )
        db.commit()
    finally:
        db.close()

    # Dispatch: scrape first → then agent analysis
    scrape_task = current_app.signature(
        "tasks.run_company_scrape",
        kwargs={"company_id": company_id},
        queue="scraper",
        immutable=True,
    )
    agent_task = current_app.signature(
        "tasks.run_agent_analysis",
        kwargs={
            "company_id": company_id,
            "report_id": report_id,
            "max_iterations": 3,
            "model_name": os.environ.get("DEFAULT_MODEL", "moonshot-v1-8k"),
        },
        queue="agent",
        immutable=True,
    )
    (scrape_task | agent_task).delay()


# ─── Company Enrichment ───────────────────────────────────────────────────────

@current_app.task(name="tasks.enrich_all_companies", bind=True, max_retries=2)
def enrich_all_companies(self):
    """
    Every 6 hours: enrich companies missing sector/description/employee_count.
    Dispatches individual enrich tasks so failures don't block the batch.
    """
    db = _get_db()
    try:
        cur = db.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("""
            SELECT id, name, domain
            FROM companies_company
            WHERE sector = '' OR sector IS NULL
               OR description = '' OR description IS NULL
               OR employee_count IS NULL
            LIMIT 50
        """)
        companies = cur.fetchall()
    finally:
        db.close()

    if not companies:
        logger.info("All companies are already enriched")
        return {"enriched": 0}

    for c in companies:
        current_app.send_task(
            "tasks.enrich_company",
            kwargs={"company_id": c["id"]},
            queue="beat",
        )
        logger.info("Dispatched enrichment for %s (%s)", c["name"], c["domain"])

    return {"dispatched": len(companies)}


@current_app.task(name="tasks.enrich_company", bind=True, max_retries=3, default_retry_delay=60)
def enrich_company(self, company_id: int):
    """
    Enrich a single company with public data:
    - Sector, description, employee count, founded year, HQ country
    Uses: Clearbit logo API (no auth), Wikipedia, and LLM fallback.
    """
    db = _get_db()
    try:
        cur = db.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM companies_company WHERE id = %s", (company_id,))
        company = cur.fetchone()
    finally:
        db.close()

    if not company:
        return

    domain = company["domain"]
    name = company["name"]
    updates = {}

    # 1. Try Clearbit Autocomplete (free, no auth) for basic enrichment
    try:
        import urllib.request
        import urllib.parse
        url = f"https://autocomplete.clearbit.com/v1/companies/suggest?query={urllib.parse.quote(name)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            if data:
                match = next((c for c in data if domain in c.get("domain", "")), data[0])
                if not company.get("description") and match.get("description"):
                    updates["description"] = match["description"][:1000]
                logger.info("Clearbit returned data for %s", name)
    except Exception as e:
        logger.warning("Clearbit enrichment failed for %s: %s", name, e)

    # 2. Try Wikipedia API for founding year and description
    try:
        import urllib.request
        import urllib.parse
        wiki_url = (
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(name)}"
        )
        req = urllib.request.Request(wiki_url, headers={"User-Agent": "NexusBot/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            wiki = json.loads(resp.read())
            if not updates.get("description") and wiki.get("extract"):
                updates["description"] = wiki["extract"][:1000]
    except Exception as e:
        logger.warning("Wikipedia enrichment failed for %s: %s", name, e)

    # 3. Use LLM to extract sector, employee_count, country, founded_year
    # from whatever description we have, or from the company name+domain alone
    if not company.get("sector") or not company.get("employee_count"):
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = ChatOpenAI(
                model=os.environ.get("DEFAULT_MODEL", "moonshot-v1-8k"),
                temperature=0,
                openai_api_key=os.environ.get("MOONSHOT_API_KEY", os.environ.get("OPENAI_API_KEY")),
                base_url=os.environ.get("OPENAI_BASE_URL"),
            )

            desc = updates.get("description") or company.get("description") or ""
            prompt = f"""Company: {name}
Domain: {domain}
Description: {desc}

Extract and return ONLY a JSON object with these fields (use null if unknown):
{{
  "sector": "e.g. SaaS, Fintech, AI/ML, E-commerce, Healthcare, etc.",
  "employee_count": <integer estimate>,
  "country": "HQ country (2-letter ISO code preferred)",
  "founded_year": <integer>
}}"""

            resp = llm.invoke([
                SystemMessage(content="You are a company data analyst. Return only valid JSON, no other text."),
                HumanMessage(content=prompt),
            ])

            raw = resp.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1].strip()
                if raw.startswith("json"):
                    raw = raw[4:].strip()

            enrichment = json.loads(raw)

            if not company.get("sector") and enrichment.get("sector"):
                updates["sector"] = str(enrichment["sector"])[:100]
            if not company.get("employee_count") and enrichment.get("employee_count"):
                try:
                    updates["employee_count"] = int(enrichment["employee_count"])
                except (TypeError, ValueError):
                    pass
            if not company.get("country") and enrichment.get("country"):
                updates["country"] = str(enrichment["country"])[:100]
            if not company.get("founded_year") and enrichment.get("founded_year"):
                try:
                    updates["founded_year"] = int(enrichment["founded_year"])
                except (TypeError, ValueError):
                    pass

        except Exception as e:
            logger.warning("LLM enrichment failed for %s: %s", name, e)

    if not updates:
        logger.info("No enrichment data found for %s", name)
        return {"company_id": company_id, "updated_fields": []}

    # Apply updates
    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [company_id]
    db = _get_db()
    try:
        cur = db.cursor()
        cur.execute(
            f"UPDATE companies_company SET {set_clause}, updated_at = NOW() WHERE id = %s",
            values,
        )
        db.commit()
        logger.info("Enriched %s: updated %s", name, list(updates.keys()))
    finally:
        db.close()

    return {"company_id": company_id, "updated_fields": list(updates.keys())}
