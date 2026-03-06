"""Integration with the logo.dev REST API."""

import os

import requests
from dotenv import load_dotenv

from logo_scraper.models import Logo, LogoSource

load_dotenv()

_BASE_URL = "https://img.logo.dev"


class LogoDevScraper:
    """Fetch logos via the logo.dev API.

    Requires a valid API key in the ``LOGODEV_API_KEY`` environment variable
    (or ``.env`` file).

    Docs: https://www.logo.dev/docs
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("LOGODEV_API_KEY")
        if not self.api_key:
            raise ValueError(
                "logo.dev API key not found. "
                "Set LOGODEV_API_KEY in your environment or .env file."
            )
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_logos(self, company: str, domain: str) -> list[Logo]:
        """Return Logo objects for *domain* using the logo.dev API.

        Args:
            company: Human-readable company name.
            domain: Bare domain, e.g. ``"stripe.com"``.

        Returns:
            List with one Logo entry when the API returns a valid image,
            empty list otherwise.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_url(self, domain: str, size: int = 200, format: str = "png") -> str:
        """Build the logo.dev image URL for *domain*.

        Args:
            domain: e.g. ``"stripe.com"``
            size: Desired image size in pixels.
            format: ``"png"`` or ``"svg"``.
        """
        raise NotImplementedError

    def _is_available(self, url: str) -> bool:
        """Return True if a HEAD request to *url* succeeds (status 200)."""
        raise NotImplementedError
