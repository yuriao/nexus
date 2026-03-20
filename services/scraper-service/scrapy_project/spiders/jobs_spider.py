"""
Jobs spider: searches for job listings to infer company growth and focus areas.
Scrapes Greenhouse.io public job boards (common for tech companies).
"""
from datetime import datetime, timezone
from urllib.parse import quote_plus

import scrapy


class JobsSpider(scrapy.Spider):
    name = "jobs_spider"
    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "CONCURRENT_REQUESTS": 1,
    }

    def __init__(self, company_id: int, company: dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.company_id = int(company_id)
        self.company = company
        self.company_name = company["name"]
        self.domain = company.get("domain", "").replace("www.", "").split(".")[0]

    def start_requests(self):
        # Try Greenhouse board (common for tech companies)
        urls = [
            f"https://boards.greenhouse.io/{self.domain}/jobs",
            f"https://jobs.lever.co/{self.domain}",
        ]
        for url in urls:
            yield scrapy.Request(
                url, callback=self.parse_greenhouse,
                errback=self.handle_error,
                meta={"dont_redirect": False},
            )

    def handle_error(self, failure):
        self.logger.warning("Jobs spider request failed: %s", failure.request.url)

    def parse_greenhouse(self, response):
        """Parse Greenhouse.io job listings."""
        jobs = []

        # Greenhouse format
        for section in response.css(".section"):
            department = section.css(".section-header::text").get("Unknown").strip()
            for job in section.css(".opening"):
                title = job.css("a::text").get("").strip()
                job_url = response.urljoin(job.css("a::attr(href)").get(""))
                location = job.css(".location::text").get("").strip()
                if title:
                    jobs.append({
                        "title": title,
                        "department": department,
                        "location": location,
                        "url": job_url,
                    })

        # Lever format
        if not jobs:
            for posting in response.css(".posting"):
                title = posting.css("h5::text").get("").strip()
                job_url = response.urljoin(posting.css("a::attr(href)").get(""))
                location = posting.css(".sort-by-location::text").get("").strip()
                department = posting.css(".sort-by-team::text").get("").strip()
                if title:
                    jobs.append({
                        "title": title,
                        "department": department,
                        "location": location,
                        "url": job_url,
                    })

        if jobs:
            raw_text = f"Job listings for {self.company_name}:\n" + "\n".join(
                f"- {j['title']} ({j['department']}) — {j['location']}" for j in jobs
            )
            yield {
                "company_id": self.company_id,
                "source_type": "jobs",
                "source_url": response.url,
                "raw_text": raw_text,
                "structured_json": {
                    "total_openings": len(jobs),
                    "jobs": jobs[:50],  # cap at 50
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                },
                "extracted_at": datetime.now(timezone.utc),
                "confidence_score": 0.95,
            }
        else:
            self.logger.info("No job listings found at %s", response.url)
