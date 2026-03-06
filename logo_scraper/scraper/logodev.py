"""Integration with the logo.dev REST API."""

import logging
import os
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from logo_scraper.models import Logo, LogoSource
from logo_scraper.utils import (
    domain_from_url,
    get_image_dimensions,
    get_image_format,
    is_valid_image,
    sanitize_filename,
)

load_dotenv()

logger = logging.getLogger(__name__)

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
        url = self._build_url(domain)
        logger.info("Checking logo.dev for %s: %s", domain, url)

        if self._is_available(url):
            logger.info("Logo available for %s", domain)
            return [Logo(company=company, source=LogoSource.LOGODEV, url=url)]

        logger.debug("No logo found for %s", domain)
        return []

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
        return f"{_BASE_URL}/{domain}?token={self.api_key}&size={size}&format={format}"

    def _is_available(self, url: str) -> bool:
        """Return True if a HEAD request to *url* succeeds (status 200)."""
        try:
            response = self._session.head(url, timeout=10)
            return response.status_code == 200
        except requests.RequestException as exc:
            logger.debug("HEAD request failed for %s: %s", url, exc)
            return False


# ---------------------------------------------------------------------------
# Standalone convenience function
# ---------------------------------------------------------------------------

def scrape_logodev(domain: str, output_dir: Path, api_key: str | None = None) -> list[Logo]:
    """Fetch and save logos from logo.dev for *domain*.

    Tries the following domain variants in order:
    1. The domain as provided (after extracting from full URL if needed).
    2. With ``www.`` prefix (if not already present).
    3. Without ``www.`` prefix (if present).
    4. ``{name}.com`` fallback when *domain* looks like a company name (no dot).

    Args:
        domain: A bare domain (``"google.com"``), full URL, or company name.
        output_dir: Directory where downloaded logo files will be saved.
        api_key: logo.dev API key. Falls back to ``LOGODEV_API_KEY`` env var.

    Returns:
        List of :class:`~logo_scraper.models.Logo` objects that were
        successfully downloaded and validated.
    """
    scraper = LogoDevScraper(api_key=api_key)

    # Normalise input to a bare domain
    if "://" in domain or "/" in domain:
        bare = domain_from_url(domain)
    elif "." not in domain:
        # Looks like a company name — try as-is then fall back to .com
        bare = domain
    else:
        bare = domain.removeprefix("www.")

    candidates = _build_domain_variants(bare)
    company = bare.split(".")[0]

    output_dir.mkdir(parents=True, exist_ok=True)
    logos: list[Logo] = []
    seen_domains: set[str] = set()

    for candidate_domain in candidates:
        if candidate_domain in seen_domains:
            continue
        seen_domains.add(candidate_domain)

        logo_candidates = scraper.fetch_logos(company=company, domain=candidate_domain)
        for logo in logo_candidates:
            filename = f"{sanitize_filename(company)}_logodev.png"
            dest = output_dir / filename

            try:
                response = scraper._session.get(logo.url, timeout=10, stream=True)
                response.raise_for_status()
                dest.write_bytes(response.content)

                if not is_valid_image(dest):
                    dest.unlink(missing_ok=True)
                    logger.warning("Downloaded content from %s is not a valid image", logo.url)
                    continue

            except requests.exceptions.Timeout:
                logger.warning("Timeout downloading logo for %s", candidate_domain)
                continue
            except requests.exceptions.HTTPError as exc:
                logger.warning("HTTP error downloading logo for %s: %s", candidate_domain, exc)
                continue
            except requests.exceptions.RequestException as exc:
                logger.warning("Network error downloading logo for %s: %s", candidate_domain, exc)
                continue
            except Exception as exc:
                logger.warning("Unexpected error downloading logo for %s: %s", candidate_domain, exc)
                continue

            dims = get_image_dimensions(dest)
            fmt = get_image_format(dest)
            logo.local_path = dest
            logo.format = fmt
            if dims:
                logo.width, logo.height = dims

            logos.append(logo)
            logger.info("Saved logo for %s -> %s (%s)", candidate_domain, dest, fmt)
            # One successful download is enough — stop trying variants
            return logos

    logger.info("No logos downloaded for %r", domain)
    return logos


def _build_domain_variants(bare: str) -> list[str]:
    """Return domain variants to try in priority order."""
    variants: list[str] = []

    if "." not in bare:
        # Company name only — try common TLDs
        variants.append(f"{bare}.com")
        return variants

    # Already a domain
    without_www = bare.removeprefix("www.")
    with_www = f"www.{without_www}"

    variants.append(without_www)
    variants.append(with_www)
    return variants
