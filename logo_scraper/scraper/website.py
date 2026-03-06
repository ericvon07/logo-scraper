"""Extract logos directly from a company's website HTML."""

import logging
import mimetypes
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from logo_scraper.models import Logo, LogoSource
from logo_scraper.utils import (
    domain_from_url,
    download_image,
    get_image_dimensions,
    get_image_format,
    sanitize_filename,
)

logger = logging.getLogger(__name__)

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_FAVICON_RELS = {"icon", "shortcut icon", "apple-touch-icon"}


class WebsiteScraper:
    """Scrape logo candidates from a website's HTML.

    Strategy (in order):
    1. ``<link rel="icon">`` / ``<link rel="shortcut icon">`` / ``<link rel="apple-touch-icon">``
    2. ``<meta property="og:image">`` / ``<meta name="og:image">``
    3. ``<meta name="twitter:image">``
    4. ``<img>`` tags whose src/alt hint at a logo (e.g. alt contains "logo")
    """

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": _BROWSER_UA})

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
        """
        logger.info("Fetching logos from %s", url)
        try:
            soup = self._get_html(url)
        except requests.RequestException as exc:
            logger.error("Failed to fetch %s: %s", url, exc)
            return []

        seen: set[str] = set()
        logos: list[Logo] = []

        candidate_urls = (
            self._extract_favicons(soup, url)
            + self._extract_og_image(soup)
            + self._extract_twitter_image(soup)
            + self._extract_logo_imgs(soup, url)
        )

        for img_url in candidate_urls:
            if img_url in seen:
                continue
            seen.add(img_url)
            logos.append(
                Logo(
                    company=company,
                    source=LogoSource.WEBSITE,
                    url=img_url,
                )
            )
            logger.debug("Found candidate: %s", img_url)

        logger.info("Found %d logo candidate(s) on %s", len(logos), url)
        return logos

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_html(self, url: str) -> BeautifulSoup:
        """Fetch *url* and return a parsed BeautifulSoup tree."""
        response = self._session.get(url, timeout=self.timeout, verify=True)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    def _extract_favicons(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Return absolute URLs of favicon/apple-touch-icon links."""
        urls: list[str] = []
        for tag in soup.find_all("link", rel=True):
            rels = {r.lower() for r in tag.get("rel", [])}
            if rels & _FAVICON_RELS:
                href = tag.get("href", "").strip()
                if href:
                    urls.append(self._make_absolute(href, base_url))
        return urls

    def _extract_og_image(self, soup: BeautifulSoup) -> list[str]:
        """Return Open Graph image URLs if present."""
        urls: list[str] = []
        for tag in soup.find_all("meta"):
            prop = tag.get("property", "") or tag.get("name", "")
            if prop.lower() in {"og:image", "og:image:url"}:
                content = tag.get("content", "").strip()
                if content:
                    urls.append(content)
        return urls

    def _extract_twitter_image(self, soup: BeautifulSoup) -> list[str]:
        """Return Twitter card image URL if present."""
        urls: list[str] = []
        for tag in soup.find_all("meta", attrs={"name": True}):
            if tag["name"].lower() == "twitter:image":
                content = tag.get("content", "").strip()
                if content:
                    urls.append(content)
        return urls

    def _extract_logo_imgs(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Return absolute URLs of ``<img>`` tags that look like logos."""
        urls: list[str] = []
        for tag in soup.find_all("img"):
            src = tag.get("src", "").strip()
            alt = tag.get("alt", "").lower()
            if not src:
                continue
            if "logo" in src.lower() or "logo" in alt:
                urls.append(self._make_absolute(src, base_url))
        return urls

    def _make_absolute(self, href: str, base_url: str) -> str:
        """Resolve *href* against *base_url* to produce an absolute URL."""
        return urljoin(base_url, href)


# ---------------------------------------------------------------------------
# Standalone convenience function
# ---------------------------------------------------------------------------

def scrape_website_logos(url: str, output_dir: Path) -> list[Logo]:
    """Scrape, download, and validate logos from *url*, saving them to *output_dir*.

    Args:
        url: Full URL of the target website.
        output_dir: Directory where logo files will be saved.

    Returns:
        List of :class:`~logo_scraper.models.Logo` objects that were
        successfully downloaded and validated.
    """
    domain = domain_from_url(url)
    company = domain.split(".")[0]
    scraper = WebsiteScraper()
    candidates = scraper.fetch_logos(company=company, url=url)

    output_dir.mkdir(parents=True, exist_ok=True)
    logos: list[Logo] = []

    for idx, logo in enumerate(candidates):
        filename = _build_filename(logo.url, company, idx)
        dest = output_dir / filename

        try:
            download_image(logo.url, dest)
        except requests.exceptions.SSLError as exc:
            logger.warning("SSL error downloading %s: %s", logo.url, exc)
            continue
        except requests.exceptions.Timeout:
            logger.warning("Timeout downloading %s", logo.url)
            continue
        except requests.exceptions.HTTPError as exc:
            logger.warning("HTTP error downloading %s: %s", logo.url, exc)
            continue
        except requests.exceptions.RequestException as exc:
            logger.warning("Network error downloading %s: %s", logo.url, exc)
            continue
        except ValueError as exc:
            # download_image raises ValueError when Pillow rejects the file
            logger.warning("Invalid image at %s: %s", logo.url, exc)
            continue
        except Exception as exc:
            logger.warning("Unexpected error downloading %s: %s", logo.url, exc)
            continue

        dims = get_image_dimensions(dest)
        fmt = get_image_format(dest)
        logo.local_path = dest
        logo.format = fmt
        if dims:
            logo.width, logo.height = dims

        logos.append(logo)
        logger.info("Saved %s -> %s (%s)", logo.url, dest, fmt)

    logger.info("Downloaded %d/%d logo(s) from %s", len(logos), len(candidates), url)
    return logos


def _build_filename(img_url: str, company: str, idx: int) -> str:
    """Derive a safe filename from the image URL."""
    parsed_path = urlparse(img_url).path
    ext = Path(parsed_path).suffix.lower()

    # Fall back to guessing extension from MIME type if URL has none
    if not ext or len(ext) > 5:
        guessed, _ = mimetypes.guess_type(img_url)
        ext = mimetypes.guess_extension(guessed or "") or ".png"

    safe_company = sanitize_filename(company)
    return f"{safe_company}_logo_{idx}{ext}"
