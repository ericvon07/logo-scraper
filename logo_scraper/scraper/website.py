"""Extract logos directly from a company's website HTML."""

from pathlib import Path

import requests
from bs4 import BeautifulSoup

from logo_scraper.models import Logo, LogoSource


class WebsiteScraper:
    """Scrape logo candidates from a website's HTML.

    Strategy (in order):
    1. ``<link rel="icon">`` / ``<link rel="apple-touch-icon">``
    2. ``<img>`` tags whose src/alt hint at a logo (e.g. alt contains "logo")
    3. Open Graph ``<meta property="og:image">``
    """

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "logo-scraper/0.1"})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_logos(self, company: str, url: str) -> list[Logo]:
        """Return a list of :class:`~logo_scraper.models.Logo` candidates found on *url*.

        Args:
            company: Human-readable company name (used for metadata).
            url: Full URL of the company website (e.g. ``"https://example.com"``).

        Returns:
            Possibly-empty list of Logo objects (not yet downloaded).

        Raises:
            requests.RequestException: On network or HTTP errors.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_html(self, url: str) -> BeautifulSoup:
        """Fetch *url* and return a parsed BeautifulSoup tree."""
        raise NotImplementedError

    def _extract_favicons(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Return absolute URLs of favicon/apple-touch-icon links."""
        raise NotImplementedError

    def _extract_logo_imgs(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Return absolute URLs of ``<img>`` tags that look like logos."""
        raise NotImplementedError

    def _extract_og_image(self, soup: BeautifulSoup) -> list[str]:
        """Return the Open Graph image URL if present."""
        raise NotImplementedError

    def _make_absolute(self, href: str, base_url: str) -> str:
        """Resolve *href* against *base_url* to produce an absolute URL."""
        raise NotImplementedError
