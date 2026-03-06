"""Extract company logos from LinkedIn company pages."""

import requests
from bs4 import BeautifulSoup

from logo_scraper.models import Logo, LogoSource


class LinkedInScraper:
    """Scrape the company logo from a LinkedIn public company page.

    Note: LinkedIn heavily rate-limits and blocks automated scraping.
    This scraper uses only the public (unauthenticated) HTML and relies
    on ``<meta>`` / ``<img>`` tags that are present before JS hydration.

    For production use, consider the LinkedIn Marketing API instead.
    """

    _BASE_URL = "https://www.linkedin.com/company"

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (compatible; logo-scraper/0.1; "
                    "+https://github.com/your-org/logo-scraper)"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_logos(self, company: str, linkedin_slug: str) -> list[Logo]:
        """Return Logo objects scraped from the LinkedIn page of *linkedin_slug*.

        Args:
            company: Human-readable company name.
            linkedin_slug: The slug in the LinkedIn URL, e.g. ``"stripe"``
                for ``https://www.linkedin.com/company/stripe``.

        Returns:
            List of Logo objects (not yet downloaded).

        Raises:
            requests.RequestException: On network or HTTP errors.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_html(self, slug: str) -> BeautifulSoup:
        """Fetch the LinkedIn company page and return a BeautifulSoup tree."""
        raise NotImplementedError

    def _extract_logo_url(self, soup: BeautifulSoup) -> str | None:
        """Parse the logo URL from the page meta tags or img elements."""
        raise NotImplementedError
