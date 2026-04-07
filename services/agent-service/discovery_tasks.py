"""
Company Discovery tasks — automatically find and add new companies to track.

Strategy:
1. Read discovery_config.json for seed queries / sectors / exclusions
2. Search Brave API for companies matching those queries
3. Extract company name + domain from results using LLM
4. Deduplicate against existing companies table
5. Insert new companies → enrichment task picks them up within 6h
6. Also: find competitors of already-tracked companies and add those too
"""
import json
import logging
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import MySQLdb

from celery import current_app

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "discovery_config.json")


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {"discovery": {"enabled": False}}


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


def _get_existing_domains() -> set:
    db = _get_db()
    try:
        cur = db.cursor()
        cur.execute("SELECT domain FROM companies_company")
        return {row[0].lower() for row in cur.fetchall()}
    finally:
        db.close()


def _insert_company(name: str, domain: str, sector: str = "", crawl_freq: int = 24) -> int | None:
    """Insert a new company if domain not already tracked. Returns new id or None."""
    db = _get_db()
    try:
        cur = db.cursor()
        cur.execute(
            """INSERT IGNORE INTO companies_company
               (name, domain, sector, country, description, crawl_frequency_hours, created_at, updated_at)
               VALUES (%s, %s, %s, '', '', %s, NOW(), NOW())""",
            (name[:255], domain[:255], sector[:100], crawl_freq),
        )
        db.commit()
        if cur.rowcount > 0:
            return cur.lastrowid
        return None
    except Exception as e:
        logger.error("Failed to insert company %s (%s): %s", name, domain, e)
        db.rollback()
        return None
    finally:
        db.close()


def _search_brave(query: str, count: int = 10) -> list[dict]:
    """Call Brave Search API and return web results."""
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        logger.warning("BRAVE_API_KEY not set, skipping Brave search")
        return []
    url = (
        f"https://api.search.brave.com/res/v1/web/search"
        f"?q={urllib.parse.quote(query)}&count={count}&search_lang=en&result_filter=web"
    )
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("web", {}).get("results", [])
    except Exception as e:
        logger.warning("Brave search failed for '%s': %s", query, e)
        return []


def _extract_domain(url: str) -> str | None:
    """Extract root domain from a URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        if host and "." in host:
            return host
    except Exception:
        pass
    return None


def _llm_extract_companies(results: list[dict], query: str, exclude_domains: set) -> list[dict]:
    """
    Use LLM to extract company names and domains from search results.
    Returns list of {name, domain, sector, confidence}.
    """
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = ChatOpenAI(
            model=os.environ.get("DEFAULT_MODEL", "moonshot-v1-8k"),
            temperature=0,
            openai_api_key=os.environ.get("MOONSHOT_API_KEY", os.environ.get("OPENAI_API_KEY")),
            base_url=os.environ.get("OPENAI_BASE_URL"),
        )

        snippets = "\n".join(
            f"- [{r.get('title','')}] {r.get('url','')} — {r.get('description','')[:200]}"
            for r in results[:15]
        )

        prompt = f"""From the search results below (query: "{query}"), extract distinct companies.

Search results:
{snippets}

Return a JSON array of companies. Each object must have:
- "name": company name (string)
- "domain": root domain only, e.g. "stripe.com" (string)
- "sector": industry sector, e.g. "Fintech", "AI/ML", "SaaS" (string)
- "confidence": 0.0-1.0 how confident this is a real trackable company (float)

Rules:
- Only include companies with a clear product/service offering
- Skip news sites, job boards, directories (techcrunch.com, linkedin.com, etc.)
- Skip government and educational institutions
- Skip giant incumbents: {', '.join(list(exclude_domains)[:10])}
- Return ONLY the JSON array, no other text."""

        resp = llm.invoke([
            SystemMessage(content="You are a company data extraction specialist. Return only valid JSON."),
            HumanMessage(content=prompt),
        ])

        raw = resp.content.strip()
        if "```" in raw:
            parts = raw.split("```")
            for part in parts[1::2]:
                candidate = part.strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate.startswith("["):
                    raw = candidate
                    break

        start, end = raw.find("["), raw.rfind("]")
        if start != -1 and end != -1:
            raw = raw[start:end + 1]

        companies = json.loads(raw)
        return [c for c in companies if isinstance(c, dict) and c.get("domain") and c.get("name")]

    except Exception as e:
        logger.error("LLM company extraction failed: %s", e)
        return []


# ─── Scheduled discovery task ─────────────────────────────────────────────────

@current_app.task(name="tasks.discover_companies", bind=True, max_retries=2)
def discover_companies(self):
    """
    Daily: discover new companies from seed queries and add them for tracking.
    Also discovers competitors of already-tracked companies.
    """
    config = _load_config()
    if not config.get("discovery", {}).get("enabled", False):
        logger.info("Company discovery disabled in config")
        return {"added": 0}

    discovery_cfg = config["discovery"]
    max_new = discovery_cfg.get("max_new_per_run", 10)
    min_confidence = discovery_cfg.get("min_confidence", 0.6)
    seed_queries = config.get("seed_queries", [])
    sectors = config.get("sectors", [])
    exclude_domains = set(config.get("exclude_domains", []))
    crawl_freq = config.get("crawl_frequency_hours", 24)

    exclude_domains |= _get_existing_domains()

    added = 0
    added_names = []

    # 1. Seed query discovery
    for query in seed_queries:
        if added >= max_new:
            break
        logger.info("Discovery search: %s", query)
        results = _search_brave(query, count=10)
        if not results:
            continue

        candidates = _llm_extract_companies(results, query, exclude_domains)
        for c in candidates:
            if added >= max_new:
                break
            domain = c.get("domain", "").lower().strip()
            if not domain or domain in exclude_domains:
                continue
            if c.get("confidence", 0) < min_confidence:
                continue

            new_id = _insert_company(
                name=c["name"],
                domain=domain,
                sector=c.get("sector", ""),
                crawl_freq=crawl_freq,
            )
            if new_id:
                added += 1
                added_names.append(c["name"])
                exclude_domains.add(domain)
                logger.info("Added company: %s (%s) sector=%s", c["name"], domain, c.get("sector"))
                # Trigger enrichment immediately
                current_app.send_task(
                    "tasks.enrich_company",
                    kwargs={"company_id": new_id},
                    queue="beat",
                )

    # 2. Competitor discovery — find competitors of tracked companies
    if config.get("competitor_tracking", {}).get("enabled", False) and added < max_new:
        db = _get_db()
        try:
            cur = db.cursor(MySQLdb.cursors.DictCursor)
            cur.execute(
                "SELECT id, name, domain, sector FROM companies_company ORDER BY RAND() LIMIT 5"
            )
            tracked = cur.fetchall()
        finally:
            db.close()

        for company in tracked:
            if added >= max_new:
                break
            query = f"competitors of {company['name']} {company.get('sector', '')} alternatives"
            logger.info("Competitor search for: %s", company["name"])
            results = _search_brave(query, count=8)
            if not results:
                continue

            candidates = _llm_extract_companies(results, query, exclude_domains)
            for c in candidates:
                if added >= max_new:
                    break
                domain = c.get("domain", "").lower().strip()
                if not domain or domain in exclude_domains:
                    continue
                if c.get("confidence", 0) < min_confidence:
                    continue

                new_id = _insert_company(
                    name=c["name"],
                    domain=domain,
                    sector=c.get("sector", "") or company.get("sector", ""),
                    crawl_freq=crawl_freq,
                )
                if new_id:
                    added += 1
                    added_names.append(c["name"])
                    exclude_domains.add(domain)
                    logger.info("Added competitor: %s (%s)", c["name"], domain)
                    current_app.send_task(
                        "tasks.enrich_company",
                        kwargs={"company_id": new_id},
                        queue="beat",
                    )

    logger.info("Discovery complete: added %d companies: %s", added, added_names)
    return {"added": added, "companies": added_names}
