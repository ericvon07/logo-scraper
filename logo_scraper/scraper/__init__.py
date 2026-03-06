"""Scraper sub-package: one module per logo source."""

from .linkedin import LinkedInScraper
from .logodev import LogoDevScraper
from .website import WebsiteScraper

__all__ = ["WebsiteScraper", "LogoDevScraper", "LinkedInScraper"]
