"""
LinkedIn Company Page Scraper.

Scrapes publicly visible company info: description, employee count, recent posts.
Does NOT require login for basic public data on company pages.
Note: LinkedIn actively blocks scrapers; this uses stealth settings and rate limiting.
"""
import logging
import time
from urllib.parse import quote

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By

from .base import BaseSeleniumScraper, retry
from rate_limiter import wait_for_rate_limit

logger = logging.getLogger(__name__)


class LinkedInCompanyScraper(BaseSeleniumScraper):
    """Scrape LinkedIn company page for: description, employee count, recent posts."""

    def scrape(self) -> list[dict]:
        results = []
        wait_for_rate_limit("linkedin")

        with self:
            try:
                company_data = self._scrape_company_page()
                if company_data:
                    results.append(company_data)
            except Exception as exc:
                logger.error("LinkedIn scrape failed for %s: %s", self.company_name, exc)
                self.take_screenshot("linkedin_error")

        return results

    @retry(max_attempts=2, delay=5.0, exceptions=(Exception,))
    def _scrape_company_page(self) -> dict | None:
        """Navigate to company page and extract public data."""
        # Build LinkedIn search URL (more reliable than direct slug)
        search_url = (
            f"https://www.linkedin.com/search/results/companies/"
            f"?keywords={quote(self.company_name)}"
        )
        if not self.navigate(search_url):
            return None

        self.human_delay(2, 4)

        # Check if we hit the login wall
        if "authwall" in self.driver.current_url or "login" in self.driver.current_url:
            logger.warning("LinkedIn login wall hit for %s", self.company_name)
            # Fall back to Google snippet about the company LinkedIn page
            return self._scrape_via_search_snippet()

        # Try to find the company card in search results
        try:
            first_result = self.wait_for(
                By.CSS_SELECTOR,
                ".reusable-search__result-container",
                timeout=10,
            )
            company_link = first_result.find_element(
                By.CSS_SELECTOR, "a.app-aware-link"
            )
            company_url = company_link.get_attribute("href")
            company_name_text = self.safe_get_text(
                first_result.find_element(By.CSS_SELECTOR, ".entity-result__title-text")
            )

            if not company_url:
                return None

            # Navigate to company page
            if not self.navigate(company_url + "about/"):
                return None

            self.human_delay(2, 4)
            return self._extract_company_about(company_url)

        except (NoSuchElementException, TimeoutException):
            logger.info("Could not find LinkedIn company for %s via search", self.company_name)
            return self._scrape_via_search_snippet()

    def _extract_company_about(self, company_url: str) -> dict | None:
        """Extract data from the company About page."""
        description = ""
        employee_count = ""
        website = ""
        industry = ""
        headquarters = ""

        try:
            # Description
            desc_el = self.driver.find_element(
                By.CSS_SELECTOR, ".org-about-us-organization-description__text"
            )
            description = self.safe_get_text(desc_el)
        except NoSuchElementException:
            pass

        try:
            # About stats (employees, etc.)
            stats = self.driver.find_elements(
                By.CSS_SELECTOR, ".org-about-company-module__company-staff-count-range"
            )
            if stats:
                employee_count = self.safe_get_text(stats[0])
        except NoSuchElementException:
            pass

        try:
            # Industry, HQ, website from definition list
            dt_elements = self.driver.find_elements(By.CSS_SELECTOR, "dt.org-page-details__definition-term")
            dd_elements = self.driver.find_elements(By.CSS_SELECTOR, "dd.org-page-details__definition-text")
            for dt, dd in zip(dt_elements, dd_elements):
                key = self.safe_get_text(dt).lower()
                val = self.safe_get_text(dd)
                if "website" in key:
                    website = val
                elif "industry" in key:
                    industry = val
                elif "headquarter" in key:
                    headquarters = val
        except NoSuchElementException:
            pass

        raw_text = (
            f"LinkedIn: {self.company_name}\n"
            f"Description: {description}\n"
            f"Employees: {employee_count}\n"
            f"Industry: {industry}\n"
            f"Headquarters: {headquarters}\n"
            f"Website: {website}"
        )

        structured = {
            "description": description,
            "employee_count": employee_count,
            "industry": industry,
            "headquarters": headquarters,
            "website": website,
            "linkedin_url": company_url,
        }

        return {
            "url": company_url,
            "raw_text": raw_text,
            "structured": structured,
        }

    def _scrape_via_search_snippet(self) -> dict | None:
        """
        Fallback: use Google search snippet for LinkedIn company info.
        Less detailed but doesn't require login.
        """
        search_url = (
            f"https://www.google.com/search?q="
            f"site:linkedin.com/company+{quote(self.company_name)}"
        )
        if not self.navigate(search_url):
            return None

        self.human_delay(1, 2)

        try:
            snippets = self.driver.find_elements(By.CSS_SELECTOR, "div.VwiC3b")
            if snippets:
                snippet_text = self.safe_get_text(snippets[0])
                return {
                    "url": search_url,
                    "raw_text": f"LinkedIn (via search): {self.company_name}\n{snippet_text}",
                    "structured": {"description": snippet_text, "source": "google_snippet"},
                }
        except Exception:
            pass

        return None
