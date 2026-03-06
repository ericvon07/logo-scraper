"""Tests for logo_scraper.scraper.website."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
from bs4 import BeautifulSoup

from logo_scraper.models import Logo, LogoSource
from logo_scraper.scraper.website import WebsiteScraper, scrape_website_logos

# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

FAVICON_HTML = """
<html><head>
  <link rel="icon" href="/favicon.ico">
  <link rel="shortcut icon" href="/favicon-32.png">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <link rel="stylesheet" href="/style.css">
</head><body></body></html>
"""

OG_IMAGE_HTML = """
<html><head>
  <meta property="og:image" content="https://cdn.example.com/og-logo.png">
  <meta name="og:image" content="https://cdn.example.com/og-name-logo.png">
</head><body></body></html>
"""

TWITTER_IMAGE_HTML = """
<html><head>
  <meta name="twitter:image" content="https://cdn.example.com/twitter-logo.png">
  <meta name="twitter:card" content="summary">
</head><body></body></html>
"""

LOGO_IMG_HTML = """
<html><body>
  <img src="/images/company-logo.png" alt="Company Logo" width="200">
  <img src="/images/banner.png" alt="Banner image">
  <img src="/logo/icon.svg" alt="icon">
  <img src="/images/photo.jpg" alt="Photo">
</body></html>
"""

COMBINED_HTML = """
<html><head>
  <link rel="icon" href="/favicon.ico">
  <meta property="og:image" content="https://cdn.example.com/og.png">
  <meta name="twitter:image" content="https://cdn.example.com/tw.png">
</head><body>
  <img src="/img/logo.png" alt="Acme logo">
</body></html>
"""

EMPTY_HTML = "<html><head></head><body><p>No images here.</p></body></html>"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_URL = "https://www.example.com"


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _mock_response(html: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(
            response=resp, request=MagicMock()
        )
    return resp


# ---------------------------------------------------------------------------
# TestWebsiteScraper._make_absolute
# ---------------------------------------------------------------------------


class TestMakeAbsolute:
    def setup_method(self) -> None:
        self.scraper = WebsiteScraper(timeout=5)

    def test_relative_path_resolved(self) -> None:
        result = self.scraper._make_absolute("/favicon.ico", BASE_URL)
        assert result == "https://www.example.com/favicon.ico"

    def test_absolute_url_unchanged(self) -> None:
        abs_url = "https://cdn.example.com/logo.png"
        assert self.scraper._make_absolute(abs_url, BASE_URL) == abs_url

    def test_relative_path_without_leading_slash(self) -> None:
        result = self.scraper._make_absolute("images/logo.png", "https://example.com/about/")
        assert result == "https://example.com/about/images/logo.png"

    def test_protocol_relative_url(self) -> None:
        result = self.scraper._make_absolute("//cdn.example.com/logo.png", BASE_URL)
        assert result == "https://cdn.example.com/logo.png"


# ---------------------------------------------------------------------------
# TestWebsiteScraper._extract_favicons
# ---------------------------------------------------------------------------


class TestExtractFavicons:
    def setup_method(self) -> None:
        self.scraper = WebsiteScraper(timeout=5)

    def test_detects_icon_rel(self) -> None:
        soup = _soup('<html><head><link rel="icon" href="/favicon.ico"></head></html>')
        urls = self.scraper._extract_favicons(soup, BASE_URL)
        assert "https://www.example.com/favicon.ico" in urls

    def test_detects_shortcut_icon(self) -> None:
        soup = _soup('<html><head><link rel="shortcut icon" href="/fav.png"></head></html>')
        urls = self.scraper._extract_favicons(soup, BASE_URL)
        assert "https://www.example.com/fav.png" in urls

    def test_detects_apple_touch_icon(self) -> None:
        soup = _soup(
            '<html><head>'
            '<link rel="apple-touch-icon" href="/apple-touch-icon.png">'
            '</head></html>'
        )
        urls = self.scraper._extract_favicons(soup, BASE_URL)
        assert "https://www.example.com/apple-touch-icon.png" in urls

    def test_ignores_stylesheet_links(self) -> None:
        soup = _soup(FAVICON_HTML)
        urls = self.scraper._extract_favicons(soup, BASE_URL)
        assert not any("style.css" in u for u in urls)

    def test_returns_all_favicon_variants(self) -> None:
        soup = _soup(FAVICON_HTML)
        urls = self.scraper._extract_favicons(soup, BASE_URL)
        assert len(urls) == 3

    def test_empty_page_returns_empty_list(self) -> None:
        soup = _soup(EMPTY_HTML)
        assert self.scraper._extract_favicons(soup, BASE_URL) == []

    def test_skips_empty_href(self) -> None:
        soup = _soup('<html><head><link rel="icon" href=""></head></html>')
        assert self.scraper._extract_favicons(soup, BASE_URL) == []


# ---------------------------------------------------------------------------
# TestWebsiteScraper._extract_og_image
# ---------------------------------------------------------------------------


class TestExtractOgImage:
    def setup_method(self) -> None:
        self.scraper = WebsiteScraper(timeout=5)

    def test_detects_og_image_property(self) -> None:
        soup = _soup(
            '<html><head>'
            '<meta property="og:image" content="https://cdn.example.com/og.png">'
            '</head></html>'
        )
        urls = self.scraper._extract_og_image(soup)
        assert "https://cdn.example.com/og.png" in urls

    def test_detects_og_image_name(self) -> None:
        soup = _soup(
            '<html><head>'
            '<meta name="og:image" content="https://cdn.example.com/og-name.png">'
            '</head></html>'
        )
        urls = self.scraper._extract_og_image(soup)
        assert "https://cdn.example.com/og-name.png" in urls

    def test_both_og_variants_detected(self) -> None:
        soup = _soup(OG_IMAGE_HTML)
        urls = self.scraper._extract_og_image(soup)
        assert len(urls) == 2

    def test_empty_page_returns_empty_list(self) -> None:
        assert self.scraper._extract_og_image(_soup(EMPTY_HTML)) == []

    def test_skips_empty_content(self) -> None:
        soup = _soup('<html><head><meta property="og:image" content=""></head></html>')
        assert self.scraper._extract_og_image(soup) == []


# ---------------------------------------------------------------------------
# TestWebsiteScraper._extract_twitter_image
# ---------------------------------------------------------------------------


class TestExtractTwitterImage:
    def setup_method(self) -> None:
        self.scraper = WebsiteScraper(timeout=5)

    def test_detects_twitter_image(self) -> None:
        soup = _soup(TWITTER_IMAGE_HTML)
        urls = self.scraper._extract_twitter_image(soup)
        assert "https://cdn.example.com/twitter-logo.png" in urls

    def test_ignores_other_twitter_meta(self) -> None:
        soup = _soup(TWITTER_IMAGE_HTML)
        urls = self.scraper._extract_twitter_image(soup)
        assert len(urls) == 1

    def test_empty_page_returns_empty_list(self) -> None:
        assert self.scraper._extract_twitter_image(_soup(EMPTY_HTML)) == []


# ---------------------------------------------------------------------------
# TestWebsiteScraper._extract_logo_imgs
# ---------------------------------------------------------------------------


class TestExtractLogoImgs:
    def setup_method(self) -> None:
        self.scraper = WebsiteScraper(timeout=5)

    def test_detects_logo_in_alt(self) -> None:
        soup = _soup(LOGO_IMG_HTML)
        urls = self.scraper._extract_logo_imgs(soup, BASE_URL)
        assert "https://www.example.com/images/company-logo.png" in urls

    def test_detects_logo_in_src(self) -> None:
        soup = _soup(LOGO_IMG_HTML)
        urls = self.scraper._extract_logo_imgs(soup, BASE_URL)
        assert "https://www.example.com/logo/icon.svg" in urls

    def test_ignores_non_logo_images(self) -> None:
        soup = _soup(LOGO_IMG_HTML)
        urls = self.scraper._extract_logo_imgs(soup, BASE_URL)
        assert not any("banner" in u for u in urls)
        assert not any("photo" in u for u in urls)

    def test_empty_page_returns_empty_list(self) -> None:
        assert self.scraper._extract_logo_imgs(_soup(EMPTY_HTML), BASE_URL) == []

    def test_skips_img_without_src(self) -> None:
        soup = _soup('<html><body><img alt="logo"></body></html>')
        assert self.scraper._extract_logo_imgs(soup, BASE_URL) == []

    def test_case_insensitive_alt_match(self) -> None:
        soup = _soup('<html><body><img src="/img/brand.png" alt="LOGO"></body></html>')
        urls = self.scraper._extract_logo_imgs(soup, BASE_URL)
        assert "https://www.example.com/img/brand.png" in urls


# ---------------------------------------------------------------------------
# TestWebsiteScraper.fetch_logos
# ---------------------------------------------------------------------------


class TestFetchLogos:
    def setup_method(self) -> None:
        self.scraper = WebsiteScraper(timeout=5)

    def _patch_get(self, html: str):
        return patch.object(
            self.scraper._session,
            "get",
            return_value=_mock_response(html),
        )

    def test_returns_list_of_logo_objects(self) -> None:
        with self._patch_get(FAVICON_HTML):
            logos = self.scraper.fetch_logos("example", BASE_URL)
        assert isinstance(logos, list)
        assert all(isinstance(lg, Logo) for lg in logos)

    def test_logos_have_correct_source(self) -> None:
        with self._patch_get(OG_IMAGE_HTML):
            logos = self.scraper.fetch_logos("example", BASE_URL)
        assert all(lg.source == LogoSource.WEBSITE for lg in logos)

    def test_logos_have_correct_company(self) -> None:
        with self._patch_get(OG_IMAGE_HTML):
            logos = self.scraper.fetch_logos("Acme Corp", BASE_URL)
        assert all(lg.company == "Acme Corp" for lg in logos)

    def test_deduplicates_urls(self) -> None:
        # Same URL appears in both og:image and as an img src
        html = """
        <html><head>
          <meta property="og:image" content="https://cdn.example.com/logo.png">
        </head><body>
          <img src="https://cdn.example.com/logo.png" alt="logo">
        </body></html>
        """
        with self._patch_get(html):
            logos = self.scraper.fetch_logos("example", BASE_URL)
        urls = [lg.url for lg in logos]
        assert len(urls) == len(set(urls))

    def test_combined_html_finds_all_sources(self) -> None:
        with self._patch_get(COMBINED_HTML):
            logos = self.scraper.fetch_logos("example", BASE_URL)
        assert len(logos) == 4  # favicon + og + twitter + img

    def test_empty_page_returns_empty_list(self) -> None:
        with self._patch_get(EMPTY_HTML):
            logos = self.scraper.fetch_logos("example", BASE_URL)
        assert logos == []

    def test_network_error_returns_empty_list(self) -> None:
        with patch.object(
            self.scraper._session,
            "get",
            side_effect=requests.ConnectionError("unreachable"),
        ):
            logos = self.scraper.fetch_logos("example", BASE_URL)
        assert logos == []

    def test_timeout_returns_empty_list(self) -> None:
        with patch.object(
            self.scraper._session,
            "get",
            side_effect=requests.Timeout("timed out"),
        ):
            logos = self.scraper.fetch_logos("example", BASE_URL)
        assert logos == []

    def test_http_404_returns_empty_list(self) -> None:
        with patch.object(
            self.scraper._session,
            "get",
            return_value=_mock_response("", status_code=404),
        ):
            logos = self.scraper.fetch_logos("example", BASE_URL)
        assert logos == []

    def test_ssl_error_returns_empty_list(self) -> None:
        with patch.object(
            self.scraper._session,
            "get",
            side_effect=requests.exceptions.SSLError("bad cert"),
        ):
            logos = self.scraper.fetch_logos("example", BASE_URL)
        assert logos == []

    def test_logos_not_downloaded_by_default(self) -> None:
        with self._patch_get(OG_IMAGE_HTML):
            logos = self.scraper.fetch_logos("example", BASE_URL)
        assert all(not lg.is_downloaded() for lg in logos)


# ---------------------------------------------------------------------------
# TestScrapeWebsiteLogos (standalone function)
# ---------------------------------------------------------------------------


class TestScrapeWebsiteLogos:
    def test_successful_download_populates_local_path(self, tmp_path: Path) -> None:
        logo = Logo(
            company="example",
            source=LogoSource.WEBSITE,
            url="https://cdn.example.com/logo.png",
        )
        with (
            patch("logo_scraper.scraper.website.WebsiteScraper.fetch_logos", return_value=[logo]),
            patch("logo_scraper.scraper.website.download_image", return_value=tmp_path / "logo.png"),
            patch("logo_scraper.scraper.website.get_image_dimensions", return_value=(200, 80)),
            patch("logo_scraper.scraper.website.get_image_format", return_value="PNG"),
        ):
            result = scrape_website_logos("https://example.com", tmp_path)

        assert len(result) == 1
        assert result[0].width == 200
        assert result[0].height == 80
        assert result[0].format == "PNG"

    def test_invalid_image_is_skipped(self, tmp_path: Path) -> None:
        logo = Logo(
            company="example",
            source=LogoSource.WEBSITE,
            url="https://cdn.example.com/notanimage.bin",
        )
        with (
            patch("logo_scraper.scraper.website.WebsiteScraper.fetch_logos", return_value=[logo]),
            patch(
                "logo_scraper.scraper.website.download_image",
                side_effect=ValueError("not a valid image"),
            ),
        ):
            result = scrape_website_logos("https://example.com", tmp_path)

        assert result == []

    def test_http_error_is_skipped(self, tmp_path: Path) -> None:
        logo = Logo(
            company="example",
            source=LogoSource.WEBSITE,
            url="https://cdn.example.com/logo.png",
        )
        with (
            patch("logo_scraper.scraper.website.WebsiteScraper.fetch_logos", return_value=[logo]),
            patch(
                "logo_scraper.scraper.website.download_image",
                side_effect=requests.HTTPError("404"),
            ),
        ):
            result = scrape_website_logos("https://example.com", tmp_path)

        assert result == []

    def test_ssl_error_is_skipped(self, tmp_path: Path) -> None:
        logo = Logo(
            company="example",
            source=LogoSource.WEBSITE,
            url="https://cdn.example.com/logo.png",
        )
        with (
            patch("logo_scraper.scraper.website.WebsiteScraper.fetch_logos", return_value=[logo]),
            patch(
                "logo_scraper.scraper.website.download_image",
                side_effect=requests.exceptions.SSLError("bad cert"),
            ),
        ):
            result = scrape_website_logos("https://example.com", tmp_path)

        assert result == []

    def test_timeout_is_skipped(self, tmp_path: Path) -> None:
        logo = Logo(
            company="example",
            source=LogoSource.WEBSITE,
            url="https://cdn.example.com/logo.png",
        )
        with (
            patch("logo_scraper.scraper.website.WebsiteScraper.fetch_logos", return_value=[logo]),
            patch(
                "logo_scraper.scraper.website.download_image",
                side_effect=requests.Timeout("timed out"),
            ),
        ):
            result = scrape_website_logos("https://example.com", tmp_path)

        assert result == []

    def test_no_candidates_returns_empty_list(self, tmp_path: Path) -> None:
        with patch("logo_scraper.scraper.website.WebsiteScraper.fetch_logos", return_value=[]):
            result = scrape_website_logos("https://example.com", tmp_path)
        assert result == []

    def test_output_dir_is_created(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "logos"
        with patch("logo_scraper.scraper.website.WebsiteScraper.fetch_logos", return_value=[]):
            scrape_website_logos("https://example.com", nested)
        assert nested.exists()

    def test_partial_failures_still_return_successes(self, tmp_path: Path) -> None:
        good = Logo(company="ex", source=LogoSource.WEBSITE, url="https://cdn.example.com/ok.png")
        bad = Logo(company="ex", source=LogoSource.WEBSITE, url="https://cdn.example.com/bad.png")

        def fake_download(url: str, dest: Path, **_) -> Path:
            if "bad" in url:
                raise requests.HTTPError("404")
            return dest

        with (
            patch(
                "logo_scraper.scraper.website.WebsiteScraper.fetch_logos",
                return_value=[good, bad],
            ),
            patch("logo_scraper.scraper.website.download_image", side_effect=fake_download),
            patch("logo_scraper.scraper.website.get_image_dimensions", return_value=None),
            patch("logo_scraper.scraper.website.get_image_format", return_value="PNG"),
        ):
            result = scrape_website_logos("https://example.com", tmp_path)

        assert len(result) == 1
        assert result[0].url == "https://cdn.example.com/ok.png"
