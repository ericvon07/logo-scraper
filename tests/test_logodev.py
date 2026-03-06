"""Tests for logo_scraper.scraper.logodev."""

import io
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from PIL import Image

from logo_scraper.models import Logo, LogoSource
from logo_scraper.scraper.logodev import LogoDevScraper, _build_domain_variants, scrape_logodev

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_API_KEY = "test-key-abc123"


def _minimal_png() -> bytes:
    """Return raw bytes of a minimal valid PNG image."""
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color=(255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _mock_head(status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    return resp


def _mock_get(content: bytes = b"", status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


# ---------------------------------------------------------------------------
# TestLogoDevScraper – unit tests for the class
# ---------------------------------------------------------------------------


class TestLogoDevScraper:
    def setup_method(self) -> None:
        self.scraper = LogoDevScraper(api_key=FAKE_API_KEY)

    # --- __init__ ---

    def test_missing_api_key_raises(self) -> None:
        """LogoDevScraper should raise ValueError when no API key is available."""
        key = os.environ.pop("LOGODEV_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="API key"):
                LogoDevScraper(api_key=None)
        finally:
            if key:
                os.environ["LOGODEV_API_KEY"] = key

    def test_explicit_api_key_is_stored(self) -> None:
        assert self.scraper.api_key == FAKE_API_KEY

    def test_env_var_api_key_is_used(self) -> None:
        with patch.dict(os.environ, {"LOGODEV_API_KEY": "env-key"}):
            scraper = LogoDevScraper(api_key=None)
        assert scraper.api_key == "env-key"

    def test_explicit_key_overrides_env_var(self) -> None:
        with patch.dict(os.environ, {"LOGODEV_API_KEY": "env-key"}):
            scraper = LogoDevScraper(api_key="explicit-key")
        assert scraper.api_key == "explicit-key"

    # --- _build_url ---

    def test_build_url_contains_domain(self) -> None:
        url = self.scraper._build_url("stripe.com")
        assert "stripe.com" in url

    def test_build_url_contains_token(self) -> None:
        url = self.scraper._build_url("stripe.com")
        assert FAKE_API_KEY in url

    def test_build_url_default_size_and_format(self) -> None:
        url = self.scraper._build_url("stripe.com")
        assert "size=200" in url
        assert "format=png" in url

    def test_build_url_custom_size_and_format(self) -> None:
        url = self.scraper._build_url("stripe.com", size=64, format="svg")
        assert "size=64" in url
        assert "format=svg" in url

    def test_build_url_starts_with_base(self) -> None:
        url = self.scraper._build_url("stripe.com")
        assert url.startswith("https://img.logo.dev/stripe.com")

    # --- _is_available ---

    def test_is_available_returns_true_on_200(self) -> None:
        with patch.object(self.scraper._session, "head", return_value=_mock_head(200)):
            assert self.scraper._is_available("https://img.logo.dev/stripe.com?token=x") is True

    def test_is_available_returns_false_on_404(self) -> None:
        with patch.object(self.scraper._session, "head", return_value=_mock_head(404)):
            assert self.scraper._is_available("https://img.logo.dev/unknown.com?token=x") is False

    def test_is_available_returns_false_on_connection_error(self) -> None:
        with patch.object(
            self.scraper._session, "head", side_effect=requests.ConnectionError("unreachable")
        ):
            assert self.scraper._is_available("https://img.logo.dev/x.com?token=x") is False

    def test_is_available_returns_false_on_timeout(self) -> None:
        with patch.object(
            self.scraper._session, "head", side_effect=requests.Timeout("timed out")
        ):
            assert self.scraper._is_available("https://img.logo.dev/x.com?token=x") is False

    # --- fetch_logos ---

    def test_fetch_logos_returns_logo_when_available(self) -> None:
        with patch.object(self.scraper._session, "head", return_value=_mock_head(200)):
            logos = self.scraper.fetch_logos("Stripe", "stripe.com")
        assert len(logos) == 1

    def test_fetch_logos_returns_empty_when_unavailable(self) -> None:
        with patch.object(self.scraper._session, "head", return_value=_mock_head(404)):
            logos = self.scraper.fetch_logos("Unknown", "unknown-brand.com")
        assert logos == []

    def test_fetch_logos_logo_has_correct_source(self) -> None:
        with patch.object(self.scraper._session, "head", return_value=_mock_head(200)):
            logos = self.scraper.fetch_logos("Stripe", "stripe.com")
        assert logos[0].source == LogoSource.LOGODEV

    def test_fetch_logos_logo_has_correct_company(self) -> None:
        with patch.object(self.scraper._session, "head", return_value=_mock_head(200)):
            logos = self.scraper.fetch_logos("Stripe Inc.", "stripe.com")
        assert logos[0].company == "Stripe Inc."

    def test_fetch_logos_logo_url_contains_domain(self) -> None:
        with patch.object(self.scraper._session, "head", return_value=_mock_head(200)):
            logos = self.scraper.fetch_logos("Stripe", "stripe.com")
        assert "stripe.com" in logos[0].url

    def test_fetch_logos_not_downloaded(self) -> None:
        """fetch_logos should not download the image – only return the URL."""
        with patch.object(self.scraper._session, "head", return_value=_mock_head(200)):
            logos = self.scraper.fetch_logos("Stripe", "stripe.com")
        assert all(not lg.is_downloaded() for lg in logos)


# ---------------------------------------------------------------------------
# TestBuildDomainVariants – unit tests for helper
# ---------------------------------------------------------------------------


class TestBuildDomainVariants:
    def test_bare_domain_returns_without_and_with_www(self) -> None:
        variants = _build_domain_variants("example.com")
        assert "example.com" in variants
        assert "www.example.com" in variants

    def test_www_domain_returns_without_and_with_www(self) -> None:
        variants = _build_domain_variants("www.example.com")
        assert "example.com" in variants
        assert "www.example.com" in variants

    def test_company_name_returns_dot_com(self) -> None:
        variants = _build_domain_variants("google")
        assert "google.com" in variants

    def test_without_www_comes_first(self) -> None:
        variants = _build_domain_variants("example.com")
        assert variants.index("example.com") < variants.index("www.example.com")


# ---------------------------------------------------------------------------
# TestScrapeLogodev – integration tests for the standalone function
# ---------------------------------------------------------------------------


class TestScrapeLogodev:
    """Tests for scrape_logodev(), with HTTP calls fully mocked."""

    def _patch_session(self, head_status: int = 200, get_content: bytes | None = None):
        """Context manager that patches the requests.Session used inside scrape_logodev."""
        if get_content is None:
            get_content = _minimal_png()

        mock_session = MagicMock()
        mock_session.head.return_value = _mock_head(head_status)
        mock_session.get.return_value = _mock_get(content=get_content)
        return patch("logo_scraper.scraper.logodev.requests.Session", return_value=mock_session)

    # --- happy path ---

    def test_valid_domain_returns_logo(self, tmp_path: Path) -> None:
        with self._patch_session(head_status=200, get_content=_minimal_png()):
            logos = scrape_logodev("stripe.com", tmp_path, api_key=FAKE_API_KEY)
        assert len(logos) == 1

    def test_valid_domain_logo_is_saved(self, tmp_path: Path) -> None:
        with self._patch_session(head_status=200, get_content=_minimal_png()):
            logos = scrape_logodev("stripe.com", tmp_path, api_key=FAKE_API_KEY)
        assert logos[0].is_downloaded()
        assert logos[0].local_path.exists()

    def test_valid_domain_logo_has_source(self, tmp_path: Path) -> None:
        with self._patch_session(head_status=200, get_content=_minimal_png()):
            logos = scrape_logodev("stripe.com", tmp_path, api_key=FAKE_API_KEY)
        assert logos[0].source == LogoSource.LOGODEV

    def test_valid_domain_populates_format(self, tmp_path: Path) -> None:
        with self._patch_session(head_status=200, get_content=_minimal_png()):
            logos = scrape_logodev("stripe.com", tmp_path, api_key=FAKE_API_KEY)
        assert logos[0].format == "PNG"

    def test_valid_domain_populates_dimensions(self, tmp_path: Path) -> None:
        with self._patch_session(head_status=200, get_content=_minimal_png()):
            logos = scrape_logodev("stripe.com", tmp_path, api_key=FAKE_API_KEY)
        assert logos[0].width == 10
        assert logos[0].height == 10

    # --- no logo found ---

    def test_domain_without_logo_returns_empty(self, tmp_path: Path) -> None:
        with self._patch_session(head_status=404):
            logos = scrape_logodev("nonexistent-brand-xyz.com", tmp_path, api_key=FAKE_API_KEY)
        assert logos == []

    # --- domain extraction from full URL ---

    def test_full_https_url_extracts_domain(self, tmp_path: Path) -> None:
        with self._patch_session(head_status=200, get_content=_minimal_png()) as mock_cls:
            scrape_logodev("https://www.google.com/search?q=logo", tmp_path, api_key=FAKE_API_KEY)
        # HEAD must be called with a URL containing the extracted domain, not "www."
        call_args = mock_cls.return_value.head.call_args_list
        called_urls = [str(c[0][0]) for c in call_args]
        assert any("google.com" in u for u in called_urls)

    def test_full_http_url_extracts_domain(self, tmp_path: Path) -> None:
        with self._patch_session(head_status=200, get_content=_minimal_png()) as mock_cls:
            scrape_logodev("http://stripe.com/pricing", tmp_path, api_key=FAKE_API_KEY)
        call_args = mock_cls.return_value.head.call_args_list
        called_urls = [str(c[0][0]) for c in call_args]
        assert any("stripe.com" in u for u in called_urls)

    def test_www_prefix_is_stripped_from_domain(self, tmp_path: Path) -> None:
        with self._patch_session(head_status=200, get_content=_minimal_png()) as mock_cls:
            scrape_logodev("www.github.com", tmp_path, api_key=FAKE_API_KEY)
        call_args = mock_cls.return_value.head.call_args_list
        called_urls = [str(c[0][0]) for c in call_args]
        # First variant tried must be without www
        assert "github.com" in called_urls[0]

    # --- company name fallback ---

    def test_company_name_tries_dot_com(self, tmp_path: Path) -> None:
        with self._patch_session(head_status=200, get_content=_minimal_png()) as mock_cls:
            scrape_logodev("stripe", tmp_path, api_key=FAKE_API_KEY)
        call_args = mock_cls.return_value.head.call_args_list
        called_urls = [str(c[0][0]) for c in call_args]
        assert any("stripe.com" in u for u in called_urls)

    def test_company_name_without_logo_returns_empty(self, tmp_path: Path) -> None:
        with self._patch_session(head_status=404):
            logos = scrape_logodev("unknowncompanyxyz", tmp_path, api_key=FAKE_API_KEY)
        assert logos == []

    # --- missing API key ---

    def test_missing_api_key_raises(self, tmp_path: Path) -> None:
        key = os.environ.pop("LOGODEV_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="API key"):
                scrape_logodev("stripe.com", tmp_path, api_key=None)
        finally:
            if key:
                os.environ["LOGODEV_API_KEY"] = key

    # --- output directory ---

    def test_output_dir_is_created(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "logos"
        with self._patch_session(head_status=404):
            scrape_logodev("stripe.com", nested, api_key=FAKE_API_KEY)
        assert nested.exists()

    # --- error handling during download ---

    def test_invalid_image_content_returns_empty(self, tmp_path: Path) -> None:
        with self._patch_session(head_status=200, get_content=b"not-an-image"):
            logos = scrape_logodev("stripe.com", tmp_path, api_key=FAKE_API_KEY)
        assert logos == []

    def test_download_http_error_returns_empty(self, tmp_path: Path) -> None:
        mock_session = MagicMock()
        mock_session.head.return_value = _mock_head(200)
        mock_session.get.return_value = _mock_get(content=b"", status_code=500)
        with patch("logo_scraper.scraper.logodev.requests.Session", return_value=mock_session):
            logos = scrape_logodev("stripe.com", tmp_path, api_key=FAKE_API_KEY)
        assert logos == []

    def test_download_timeout_returns_empty(self, tmp_path: Path) -> None:
        mock_session = MagicMock()
        mock_session.head.return_value = _mock_head(200)
        mock_session.get.side_effect = requests.Timeout("timed out")
        with patch("logo_scraper.scraper.logodev.requests.Session", return_value=mock_session):
            logos = scrape_logodev("stripe.com", tmp_path, api_key=FAKE_API_KEY)
        assert logos == []

    def test_download_network_error_returns_empty(self, tmp_path: Path) -> None:
        mock_session = MagicMock()
        mock_session.head.return_value = _mock_head(200)
        mock_session.get.side_effect = requests.ConnectionError("unreachable")
        with patch("logo_scraper.scraper.logodev.requests.Session", return_value=mock_session):
            logos = scrape_logodev("stripe.com", tmp_path, api_key=FAKE_API_KEY)
        assert logos == []

    # --- stops on first success ---

    def test_stops_after_first_successful_variant(self, tmp_path: Path) -> None:
        """Once a logo is downloaded, remaining domain variants are not tried."""
        call_count = 0

        def head_side_effect(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return _mock_head(200)

        mock_session = MagicMock()
        mock_session.head.side_effect = head_side_effect
        mock_session.get.return_value = _mock_get(content=_minimal_png())

        with patch("logo_scraper.scraper.logodev.requests.Session", return_value=mock_session):
            logos = scrape_logodev("stripe.com", tmp_path, api_key=FAKE_API_KEY)

        assert len(logos) == 1
        assert call_count == 1  # Only the first variant was tried
