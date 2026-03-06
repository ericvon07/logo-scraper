"""Orchestrator: coordinates the three logo sources with priority-based early return."""

import logging
from pathlib import Path

from logo_scraper.models import ScrapeResult
from logo_scraper.scraper.linkedin import scrape_linkedin_logo
from logo_scraper.scraper.logodev import scrape_logodev
from logo_scraper.scraper.website import scrape_website_logos
from logo_scraper.utils import domain_from_url

logger = logging.getLogger(__name__)


def fetch_logos(
    company_name: str,
    website_url: str | None = None,
    linkedin_url: str | None = None,
    output_dir: str = "./output",
    logodev_api_key: str | None = None,
) -> ScrapeResult:
    """Fetch logos for a company, trying sources in priority order.

    Priority (early return — stops at the first source that yields a logo):
    1. logo.dev  (domain extracted from *website_url*, or ``{company_name}.com``)
    2. Company website HTML scraping (requires *website_url*)
    3. LinkedIn  (requires *linkedin_url*)

    Args:
        company_name: Human-readable company name.
        website_url:  Company website URL (used for logo.dev domain lookup and
                      direct HTML scraping).
        linkedin_url: LinkedIn company page URL (used as last-resort fallback).
        output_dir:   Directory where downloaded logos will be saved.
        logodev_api_key: logo.dev API key. Falls back to ``LOGODEV_API_KEY``
                      environment variable when *None*.

    Returns:
        :class:`~logo_scraper.models.ScrapeResult` with all logos found and
        the source that succeeded (logos carry their own ``source`` attribute).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    domain = domain_from_url(website_url) if website_url else f"{company_name.lower()}.com"
    result = ScrapeResult(company=company_name, domain=domain)

    # ------------------------------------------------------------------
    # 1. logo.dev
    # ------------------------------------------------------------------
    try:
        logos = scrape_logodev(
            domain=website_url or domain,
            output_dir=out,
            api_key=logodev_api_key,
        )
        if logos:
            logger.info("logo.dev found %d logo(s) for %s", len(logos), company_name)
            result.logos = logos
            return result
    except ValueError as exc:
        # API key missing — log and continue to next source
        logger.warning("logo.dev skipped: %s", exc)
        result.errors.append(f"logodev: {exc}")
    except Exception as exc:
        logger.warning("logo.dev error for %s: %s", company_name, exc)
        result.errors.append(f"logodev: {exc}")

    # ------------------------------------------------------------------
    # 2. Website HTML scraping
    # ------------------------------------------------------------------
    if website_url:
        try:
            logos = scrape_website_logos(url=website_url, output_dir=out)
            if logos:
                logger.info("Website found %d logo(s) for %s", len(logos), company_name)
                result.logos = logos
                return result
        except Exception as exc:
            logger.warning("Website scraping error for %s: %s", company_name, exc)
            result.errors.append(f"website: {exc}")

    # ------------------------------------------------------------------
    # 3. LinkedIn fallback
    # ------------------------------------------------------------------
    if linkedin_url:
        try:
            logos = scrape_linkedin_logo(linkedin_url=linkedin_url, output_dir=out)
            if logos:
                logger.info("LinkedIn found %d logo(s) for %s", len(logos), company_name)
                result.logos = logos
                return result
        except Exception as exc:
            logger.warning("LinkedIn scraping error for %s: %s", company_name, exc)
            result.errors.append(f"linkedin: {exc}")

    logger.info("No logos found for %s from any source", company_name)
    return result
