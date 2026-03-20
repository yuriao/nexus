"""
BaseSeleniumScraper: headless Chrome with stealth settings, retry logic,
and helpers used by all Selenium scrapers.
"""
import logging
import os
import random
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from fake_useragent import UserAgent
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

SCREENSHOT_DIR = Path("/tmp/nexus_screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def retry(max_attempts: int = 3, delay: float = 2.0, exceptions=(Exception,)):
    """Decorator: retry on specified exceptions with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    wait = delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                    logger.warning(
                        "%s attempt %d/%d failed: %s. Retrying in %.1fs",
                        func.__name__, attempt, max_attempts, exc, wait,
                    )
                    time.sleep(wait)
            raise last_exc
        return wrapper
    return decorator


class BaseSeleniumScraper:
    """Base class for all Selenium-based scrapers in Nexus."""

    def __init__(self, company_id: int, company: dict):
        self.company_id = company_id
        self.company = company
        self.company_name = company.get("name", "")
        self.driver: webdriver.Chrome | None = None
        self._ua = UserAgent(fallback="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")

    def _build_options(self) -> Options:
        opts = Options()
        headless = os.environ.get("SELENIUM_HEADLESS", "true").lower() == "true"
        if headless:
            opts.add_argument("--headless=new")

        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument(f"--user-agent={self._ua.random}")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        return opts

    def start(self) -> None:
        """Launch Chrome WebDriver."""
        if self.driver is not None:
            return
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=self._build_options())
            # Defeat navigator.webdriver detection
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            timeout = int(os.environ.get("SELENIUM_PAGE_LOAD_TIMEOUT", "30"))
            self.driver.set_page_load_timeout(timeout)
            implicit_wait = int(os.environ.get("SELENIUM_IMPLICIT_WAIT", "10"))
            self.driver.implicitly_wait(implicit_wait)
            logger.info("Chrome started for %s", self.company_name)
        except WebDriverException as exc:
            logger.error("Failed to start Chrome: %s", exc)
            raise

    def stop(self) -> None:
        """Quit WebDriver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None

    def take_screenshot(self, label: str = "error") -> str | None:
        """Save a screenshot for debugging. Returns path or None."""
        if not self.driver:
            return None
        try:
            path = SCREENSHOT_DIR / f"{self.company_id}_{label}_{int(time.time())}.png"
            self.driver.save_screenshot(str(path))
            logger.info("Screenshot saved: %s", path)
            return str(path)
        except Exception as exc:
            logger.warning("Screenshot failed: %s", exc)
            return None

    def wait_for(self, by: By, value: str, timeout: int = 15) -> Any:
        """Wait for element to be present."""
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.presence_of_element_located((by, value)))

    def wait_for_clickable(self, by: By, value: str, timeout: int = 15) -> Any:
        """Wait for element to be clickable."""
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.element_to_be_clickable((by, value)))

    def safe_get_text(self, element, default: str = "") -> str:
        """Get text from element, handling stale references."""
        try:
            return element.text.strip()
        except StaleElementReferenceException:
            return default

    def human_delay(self, min_s: float = 0.5, max_s: float = 2.0) -> None:
        """Random delay to mimic human behaviour."""
        time.sleep(random.uniform(min_s, max_s))

    def navigate(self, url: str) -> bool:
        """Navigate to URL with error handling."""
        try:
            self.driver.get(url)
            self.human_delay(1.0, 3.0)
            return True
        except TimeoutException:
            logger.warning("Page load timeout: %s", url)
            self.take_screenshot("timeout")
            return False
        except WebDriverException as exc:
            logger.error("Navigation error for %s: %s", url, exc)
            self.take_screenshot("nav_error")
            return False

    def scrape(self) -> list[dict]:
        """Override in subclass. Returns list of result dicts."""
        raise NotImplementedError

    def __enter__(self) -> "BaseSeleniumScraper":
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop()
