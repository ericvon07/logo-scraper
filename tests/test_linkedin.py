"""Tests for logo_scraper.scraper.linkedin."""

import pytest

from logo_scraper.scraper.linkedin import LinkedInScraper


class TestLinkedInScraper:
    def setup_method(self) -> None:
        self.scraper = LinkedInScraper(timeout=5)

    def test_fetch_logos_returns_list(self) -> None:
        """fetch_logos should return a list (possibly empty)."""
        pytest.skip("Not implemented yet.")

    def test_extract_logo_url_from_meta(self) -> None:
        """Logo URL should be extracted from og:image or similar meta tags."""
        pytest.skip("Not implemented yet.")

    def test_extract_logo_url_not_found(self) -> None:
        """_extract_logo_url should return None when no logo tag is present."""
        pytest.skip("Not implemented yet.")
