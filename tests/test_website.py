"""Tests for logo_scraper.scraper.website."""

import pytest

from logo_scraper.scraper.website import WebsiteScraper


class TestWebsiteScraper:
    def setup_method(self) -> None:
        self.scraper = WebsiteScraper(timeout=5)

    def test_fetch_logos_returns_list(self) -> None:
        """fetch_logos should return a list (possibly empty)."""
        pytest.skip("Not implemented yet.")

    def test_make_absolute_with_relative_path(self) -> None:
        """Relative hrefs should be resolved against the base URL."""
        pytest.skip("Not implemented yet.")

    def test_make_absolute_with_absolute_url(self) -> None:
        """Absolute hrefs should be returned unchanged."""
        pytest.skip("Not implemented yet.")

    def test_extract_favicons(self) -> None:
        """Favicon <link> tags should be detected."""
        pytest.skip("Not implemented yet.")

    def test_extract_og_image(self) -> None:
        """Open Graph image meta tag should be detected."""
        pytest.skip("Not implemented yet.")
