"""
Crunchbase spider: scrapes public company data from Crunchbase.
Note: Only scrapes publicly available data. Respects robots.txt.
"""
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy


class CrunchbaseSpider(scrapy.Spider):
    name = "crunchbase_spider"
    custom_settings = {
        "DOWNLOAD_DELAY": 5,
        "CONCURRENT_REQUESTS": 1,
        "ROBOTSTXT_OBEY": True,
    }

    def __init__(self, company_id: int, company: dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.company_id = int(company_id)
        self.company = company
        self.company_name = company["name"]
        # Normalise domain to crunchbase slug
        domain = company.get("domain", "").replace("www.", "").split(".")[0]
        self.cb_slug = domain.lower().replace(" ", "-")

    def start_requests(self):
        url = f"https://www.crunchbase.com/organization/{self.cb_slug}"
        yield scrapy.Request(url, callback=self.parse_org, errback=self.handle_error)

    def handle_error(self, failure):
        self.logger.warning("Crunchbase request failed: %s", failure.request.url)

    def parse_org(self, response):
        """Parse Crunchbase organization page (public data only)."""
        # Crunchbase renders via React, but meta tags contain useful info
        name = (
            response.css('meta[property="og:title"]::attr(content)').get("")
            or self.company_name
        )
        description = response.css('meta[property="og:description"]::attr(content)').get("").strip()

        # Try to extract JSON-LD structured data
        import json
        structured_data = {}
        for script in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(script)
                if isinstance(data, dict):
                    structured_data.update(data)
            except (json.JSONDecodeError, ValueError):
                pass

        raw_text = f"{name}\n\n{description}"
        if len(raw_text.strip()) < 20:
            self.logger.info("No useful Crunchbase data for %s", self.company_name)
            return

        yield {
            "company_id": self.company_id,
            "source_type": "crunchbase",
            "source_url": response.url,
            "raw_text": raw_text,
            "structured_json": {
                "name": name,
                "description": description,
                "url": response.url,
                "structured_ld": structured_data,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            },
            "extracted_at": datetime.now(timezone.utc),
            "confidence_score": 0.8,
        }
