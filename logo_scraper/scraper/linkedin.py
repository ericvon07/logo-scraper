"""Extract company logos from LinkedIn company pages.

WARNING: Esta é a fonte menos confiável do scraper.
O LinkedIn bloqueia scraping agressivamente (rate limiting, CAPTCHAs, redirect
para login). A taxa de sucesso é baixa e pode variar sem aviso prévio.

Para uso em produção, considere a LinkedIn Marketing API (requer aprovação)
ou fontes alternativas (logo.dev, website direto).
"""

import json
import logging
import mimetypes
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from logo_scraper.models import Logo, LogoSource
from logo_scraper.utils import (
    domain_from_url,
    get_image_dimensions,
    get_image_format,
    is_valid_image,
    sanitize_filename,
)

logger = logging.getLogger(__name__)

# Headers realistas de navegador para reduzir chance de bloqueio imediato.
# Ainda assim, o LinkedIn frequentemente redireciona para login ou retorna 403.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Delay respeitoso antes de cada requisição (reduz risco de rate limiting)
_REQUEST_DELAY_SECONDS = 1.5

# Códigos HTTP que indicam bloqueio pelo LinkedIn
_BLOCKED_STATUS_CODES = {403, 999}


class LinkedInScraper:
    """Scrape the company logo from a LinkedIn public company page.

    Note: LinkedIn heavily rate-limits and blocks automated scraping.
    This scraper uses only the public (unauthenticated) HTML and relies
    on ``<meta>`` / ``<img>`` tags and JSON-LD data present in the initial HTML.

    For production use, consider the LinkedIn Marketing API instead.
    """

    _BASE_URL = "https://www.linkedin.com/company"

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(_BROWSER_HEADERS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_logos(self, company: str, linkedin_url: str) -> list[Logo]:
        """Return Logo objects scraped from a LinkedIn company page URL.

        Args:
            company: Human-readable company name.
            linkedin_url: Full LinkedIn company URL, e.g.
                ``"https://www.linkedin.com/company/stripe"``.

        Returns:
            List of Logo objects (not yet downloaded). Empty list if
            LinkedIn blocks the request or no logo is found.
        """
        logger.info("Fetching LinkedIn page: %s", linkedin_url)

        try:
            soup = self._get_html(linkedin_url)
        except _LinkedInBlocked as exc:
            logger.warning(
                "LinkedIn blocked the request for %s (%s). "
                "This is expected — returning empty list.",
                linkedin_url,
                exc,
            )
            return []
        except requests.RequestException as exc:
            logger.warning("Network error fetching %s: %s", linkedin_url, exc)
            return []

        seen: set[str] = set()
        logos: list[Logo] = []

        candidate_urls = (
            self._extract_og_image(soup)
            + self._extract_json_ld_images(soup)
            + self._extract_logo_imgs(soup, linkedin_url)
        )

        for img_url in candidate_urls:
            if img_url in seen:
                continue
            seen.add(img_url)
            logos.append(Logo(company=company, source=LogoSource.LINKEDIN, url=img_url))
            logger.debug("LinkedIn logo candidate: %s", img_url)

        logger.info(
            "Found %d logo candidate(s) on LinkedIn for %s", len(logos), linkedin_url
        )
        return logos

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_html(self, url: str) -> BeautifulSoup:
        """Fetch *url* with a polite delay and return a parsed BeautifulSoup tree.

        Raises:
            _LinkedInBlocked: If LinkedIn responds with a block/redirect signal.
            requests.RequestException: On other network errors.
        """
        time.sleep(_REQUEST_DELAY_SECONDS)

        try:
            response = self._session.get(
                url, timeout=self.timeout, verify=True, allow_redirects=True
            )
        except requests.RequestException:
            raise

        # Detect explicit blocks
        if response.status_code in _BLOCKED_STATUS_CODES:
            raise _LinkedInBlocked(f"HTTP {response.status_code}")

        # Detect redirect to login page (common LinkedIn anti-scraping measure)
        final_url = response.url
        if "linkedin.com/authwall" in final_url or "linkedin.com/login" in final_url:
            raise _LinkedInBlocked(f"Redirected to login: {final_url}")

        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    def _extract_og_image(self, soup: BeautifulSoup) -> list[str]:
        """Return Open Graph / meta image URLs."""
        urls: list[str] = []
        for tag in soup.find_all("meta"):
            prop = tag.get("property", "") or tag.get("name", "")
            if prop.lower() in {"og:image", "og:image:url"}:
                content = tag.get("content", "").strip()
                if content:
                    urls.append(content)
        return urls

    def _extract_json_ld_images(self, soup: BeautifulSoup) -> list[str]:
        """Return image URLs found in JSON-LD structured data blocks."""
        urls: list[str] = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue

            for candidate in _walk_json(data):
                if isinstance(candidate, str) and candidate.startswith("http"):
                    urls.append(candidate)

        return urls

    def _extract_logo_imgs(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Return absolute URLs of ``<img>`` tags whose class or src hint at a logo."""
        from urllib.parse import urljoin

        urls: list[str] = []
        for tag in soup.find_all("img"):
            src = tag.get("src", "").strip()
            if not src:
                continue
            classes = " ".join(tag.get("class", []))
            alt = tag.get("alt", "").lower()
            if "logo" in src.lower() or "logo" in classes.lower() or "logo" in alt:
                urls.append(urljoin(base_url, src))
        return urls

    def _extract_logo_url(self, soup: BeautifulSoup) -> str | None:
        """Return the first logo URL found in the page, or None."""
        candidates = (
            self._extract_og_image(soup)
            + self._extract_json_ld_images(soup)
            + self._extract_logo_imgs(soup, self._BASE_URL)
        )
        return candidates[0] if candidates else None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _LinkedInBlocked(Exception):
    """Raised when LinkedIn returns a block signal (403, authwall redirect, etc.)."""


def _walk_json(obj: object) -> list[str]:
    """Recursively collect string values for keys named 'logo' or 'image' in JSON."""
    results: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.lower() in {"logo", "image", "url"} and isinstance(value, str):
                results.append(value)
            else:
                results.extend(_walk_json(value))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_walk_json(item))
    return results


# ---------------------------------------------------------------------------
# Standalone convenience function
# ---------------------------------------------------------------------------

def scrape_linkedin_logo(linkedin_url: str, output_dir: Path) -> list[Logo]:
    """Scrape, download, and validate logos from a LinkedIn company page.

    NOTE: Esta é a fonte menos confiável — o LinkedIn bloqueia scraping
    agressivamente. Em caso de bloqueio (403, redirect para login), retorna
    lista vazia sem lançar exceção.

    Args:
        linkedin_url: Full LinkedIn company URL,
            e.g. ``"https://www.linkedin.com/company/stripe"``.
        output_dir: Directory where logo files will be saved.

    Returns:
        List of :class:`~logo_scraper.models.Logo` objects that were
        successfully downloaded and validated. Empty list on block or error.
    """
    parsed = urlparse(linkedin_url)
    # Derive a company slug from the URL path: /company/stripe -> "stripe"
    path_parts = [p for p in parsed.path.split("/") if p]
    company = path_parts[-1] if path_parts else domain_from_url(linkedin_url).split(".")[0]

    scraper = LinkedInScraper()
    candidates = scraper.fetch_logos(company=company, linkedin_url=linkedin_url)

    if not candidates:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    logos: list[Logo] = []

    for idx, logo in enumerate(candidates):
        filename = _build_filename(logo.url, company, idx)
        dest = output_dir / filename

        try:
            response = requests.get(logo.url, timeout=10, stream=True)
            response.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(response.content)

            if not is_valid_image(dest):
                dest.unlink(missing_ok=True)
                logger.warning("Invalid image content at %s — skipping", logo.url)
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
        logger.info("Saved LinkedIn logo -> %s (%s)", dest, fmt)

    logger.info(
        "Downloaded %d/%d LinkedIn logo(s) from %s",
        len(logos),
        len(candidates),
        linkedin_url,
    )
    return logos


def _build_filename(img_url: str, company: str, idx: int) -> str:
    """Derive a safe filename from the image URL."""
    parsed_path = urlparse(img_url).path
    ext = Path(parsed_path).suffix.lower()
    if not ext or len(ext) > 5:
        guessed, _ = mimetypes.guess_type(img_url)
        ext = mimetypes.guess_extension(guessed or "") or ".png"
    safe_company = sanitize_filename(company)
    return f"{safe_company}_linkedin_{idx}{ext}"
