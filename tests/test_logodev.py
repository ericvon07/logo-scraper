"""Tests for logo_scraper.scraper.logodev."""

import pytest

from logo_scraper.scraper.logodev import LogoDevScraper


class TestLogoDev:
    def test_missing_api_key_raises(self) -> None:
        """LogoDevScraper should raise ValueError when no API key is available."""
        import os

        key = os.environ.pop("LOGODEV_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="API key"):
                LogoDevScraper(api_key=None)
        finally:
            if key:
                os.environ["LOGODEV_API_KEY"] = key

    def test_build_url_format(self) -> None:
        """_build_url should include domain and token in the URL."""
        pytest.skip("Not implemented yet.")

    def test_fetch_logos_returns_list(self) -> None:
        """fetch_logos should return a list of Logo objects."""
        pytest.skip("Not implemented yet.")
