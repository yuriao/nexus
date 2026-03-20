"""
Web search tool using Brave Search API.
"""
import logging
import os
from typing import Any

import requests
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

BRAVE_API_BASE = "https://api.search.brave.com/res/v1"


@tool
def web_search(query: str) -> list[dict]:
    """
    Search the web using Brave Search API.
    Returns a list of results with keys: title, url, snippet.
    Use this to find recent news, announcements, or public information about a company.
    """
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        logger.warning("BRAVE_API_KEY not set — returning empty results")
        return []

    try:
        resp = requests.get(
            f"{BRAVE_API_BASE}/web/search",
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            params={
                "q": query,
                "count": 10,
                "search_lang": "en",
                "result_filter": "web",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("web", {}).get("results", []):
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", ""),
                    "age": item.get("age", ""),
                }
            )
        logger.info("web_search('%s') → %d results", query, len(results))
        return results

    except requests.RequestException as exc:
        logger.error("Brave Search API error: %s", exc)
        return [{"error": str(exc), "title": "", "url": "", "snippet": ""}]


@tool
def fetch_url(url: str) -> str:
    """
    Fetch the text content of a URL.
    Use this after web_search to read the full content of a relevant page.
    Returns the page text (truncated to 5000 chars).
    """
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NexusBot/1.0)"},
            timeout=15,
            allow_redirects=True,
        )
        resp.raise_for_status()

        # Basic HTML → text stripping
        import re
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:5000]

    except Exception as exc:
        logger.error("fetch_url error for %s: %s", url, exc)
        return f"Error fetching {url}: {exc}"
