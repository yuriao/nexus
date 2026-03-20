"""
News spider: searches for recent news articles about a company.
Uses Bing News search (no auth required) to find URLs, then follows them.
"""
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import scrapy


class NewsSpider(scrapy.Spider):
    name = "news_spider"
    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 2,
    }

    def __init__(self, company_id: int, company: dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.company_id = int(company_id)
        self.company = company
        self.company_name = company["name"]
        self.domain = company.get("domain", "")

    def start_requests(self):
        queries = [
            f'"{self.company_name}" news',
            f'"{self.company_name}" announcement',
            f'site:techcrunch.com OR site:reuters.com "{self.company_name}"',
        ]
        for q in queries:
            url = f"https://www.bing.com/news/search?q={quote_plus(q)}&format=rss"
            yield scrapy.Request(url, callback=self.parse_rss, meta={"query": q})

    def parse_rss(self, response):
        """Parse Bing News RSS feed."""
        response.selector.remove_namespaces()
        items = response.css("item")
        if not items:
            self.logger.warning("No RSS items found for query: %s", response.meta["query"])
            return

        for item in items[:10]:  # max 10 items per query
            title = item.css("title::text").get("").strip()
            url = item.css("link::text").get("") or item.css("guid::text").get("")
            snippet = item.css("description::text").get("").strip()
            pub_date_str = item.css("pubDate::text").get("")

            # Try to parse publish date
            pub_date = None
            for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"]:
                try:
                    pub_date = datetime.strptime(pub_date_str.strip(), fmt)
                    break
                except (ValueError, AttributeError):
                    pass
            if pub_date is None:
                pub_date = datetime.now(timezone.utc)

            # Clean HTML from snippet
            clean_snippet = re.sub(r"<[^>]+>", "", snippet)

            raw_text = f"{title}\n\n{clean_snippet}"
            structured = {
                "title": title,
                "url": url,
                "snippet": clean_snippet,
                "published_at": pub_date.isoformat() if pub_date else None,
            }

            if url and len(raw_text.strip()) > 20:
                yield {
                    "company_id": self.company_id,
                    "source_type": "news",
                    "source_url": url,
                    "raw_text": raw_text,
                    "structured_json": structured,
                    "extracted_at": datetime.now(timezone.utc),
                    "confidence_score": 0.9,
                }
