"""
Custom Scrapy middlewares.
"""
import logging
import random

from fake_useragent import UserAgent
from scrapy.downloadermiddlewares.retry import RetryMiddleware as BaseRetryMiddleware
from scrapy.utils.response import response_status_message

logger = logging.getLogger(__name__)


class RandomUserAgentMiddleware:
    """Rotate User-Agent header on every request."""

    def __init__(self):
        self.ua = UserAgent(fallback="Mozilla/5.0")

    def process_request(self, request, spider):
        ua = self.ua.random
        request.headers["User-Agent"] = ua


class RetryMiddleware(BaseRetryMiddleware):
    """Extended retry middleware that adds jitter between retries."""

    def process_response(self, request, response, spider):
        if response.status in [429, 503]:
            logger.warning("Rate limited (%s) on %s", response.status, request.url)
            retry_after = int(response.headers.get("Retry-After", 10))
            import time
            time.sleep(retry_after + random.uniform(1, 5))
        return super().process_response(request, response, spider)
