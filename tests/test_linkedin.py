"""Tests for logo_scraper.scraper.linkedin.

All network calls are mocked — no real HTTP requests are made.
time.sleep is also patched out so the polite delay doesn't slow the suite.

Scenarios covered:
  1. og:image extraction from realistic LinkedIn HTML
  2. JSON-LD block with a logo key
  3. HTTP 403 / 999 blocked responses
  4. Invalid / unreachable URLs (connection error, malformed)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from logo_scraper.models import LogoSource
from logo_scraper.scraper.linkedin import (
    LinkedInScraper,
    _LinkedInBlocked,
    _walk_json,
    scrape_linkedin_logo,
)

# ---------------------------------------------------------------------------
# HTML fixtures — realistic snippets of what LinkedIn actually serves
# ---------------------------------------------------------------------------

# A trimmed LinkedIn company page that carries og:image in the <head>
_HTML_OG_IMAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Stripe | LinkedIn</title>
  <meta property="og:title" content="Stripe"/>
  <meta property="og:image" content="https://media.licdn.com/dms/image/stripe-logo-800x800.png"/>
  <meta property="og:image:width" content="800"/>
  <meta property="og:image:height" content="800"/>
  <meta property="og:type" content="company"/>
</head>
<body><div id="main"></div></body>
</html>
"""

# Page that also carries og:image:url (alternate property name)
_HTML_OG_IMAGE_URL = """\
<!DOCTYPE html>
<html><head>
  <meta property="og:image:url" content="https://media.licdn.com/dms/image/alt-logo.jpg"/>
</head><body></body></html>
"""

# Page with both og:image AND og:image:url pointing to the same CDN URL
_HTML_OG_IMAGE_DUPLICATE = """\
<!DOCTYPE html>
<html><head>
  <meta property="og:image"     content="https://media.licdn.com/dms/image/same.png"/>
  <meta property="og:image:url" content="https://media.licdn.com/dms/image/same.png"/>
</head><body></body></html>
"""

# A page with a JSON-LD Organization block that contains a logo key
_HTML_JSON_LD_LOGO = """\
<!DOCTYPE html>
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Stripe",
  "url": "https://stripe.com",
  "logo": "https://media.licdn.com/dms/image/jsonld-logo.png",
  "sameAs": ["https://twitter.com/stripe"]
}
</script>
</head><body></body></html>
"""

# JSON-LD with a nested ImageObject under "logo"
_HTML_JSON_LD_IMAGE_OBJECT = """\
<!DOCTYPE html>
<html><head>
<script type="application/ld+json">
{
  "@type": "Organization",
  "logo": {
    "@type": "ImageObject",
    "url": "https://media.licdn.com/dms/image/nested-logo.png"
  }
}
</script>
</head><body></body></html>
"""

# JSON-LD block that is intentionally broken JSON
_HTML_JSON_LD_INVALID = """\
<!DOCTYPE html>
<html><head>
<script type="application/ld+json">{ "logo": INVALID_VALUE }</script>
</head><body></body></html>
"""

# <img> tag whose class name contains "logo" — typical LinkedIn DOM structure
_HTML_IMG_LOGO_CLASS = """\
<!DOCTYPE html>
<html><body>
  <img class="org-top-card-summary-info-list__logo"
       src="https://media.licdn.com/dms/image/img-logo.png"
       alt="Stripe logo">
</body></html>
"""

# Page with only irrelevant images (no logo signals)
_HTML_NO_LOGO = """\
<!DOCTYPE html>
<html><head><title>Stripe | LinkedIn</title></head>
<body><img src="/static/banner.jpg" alt="Banner"></body>
</html>
"""

# What LinkedIn returns after redirecting to the authwall
_HTML_AUTHWALL = """\
<!DOCTYPE html>
<html><body><h1>Join LinkedIn</h1></body></html>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(
    status_code: int = 200,
    text: str = "",
    url: str = "https://www.linkedin.com/company/stripe",
) -> MagicMock:
    """Build a fake requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.url = url
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


# ---------------------------------------------------------------------------
# Shared fixture: suppress time.sleep for all tests in this module
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def no_sleep():
    """Patch time.sleep so the polite delay doesn't slow down tests."""
    with patch("logo_scraper.scraper.linkedin.time.sleep"):
        yield


# ---------------------------------------------------------------------------
# 1. og:image extraction
# ---------------------------------------------------------------------------

class TestOgImageExtraction:
    """LinkedIn page with og:image meta tag — the most common happy path."""

    def setup_method(self) -> None:
        self.scraper = LinkedInScraper(timeout=5)
        self.url = "https://www.linkedin.com/company/stripe"

    def _mock_get(self, html: str, final_url: str | None = None) -> MagicMock:
        resp = _make_response(text=html, url=final_url or self.url)
        self.scraper._session.get = MagicMock(return_value=resp)
        return resp

    def test_og_image_property_extracted(self) -> None:
        """og:image content becomes a Logo candidate."""
        self._mock_get(_HTML_OG_IMAGE)
        logos = self.scraper.fetch_logos("Stripe", self.url)

        assert len(logos) == 1
        assert logos[0].url == "https://media.licdn.com/dms/image/stripe-logo-800x800.png"

    def test_og_image_logo_source_is_linkedin(self) -> None:
        """Logo.source must be LINKEDIN, not WEBSITE or LOGODEV."""
        self._mock_get(_HTML_OG_IMAGE)
        logos = self.scraper.fetch_logos("Stripe", self.url)

        assert logos[0].source is LogoSource.LINKEDIN

    def test_og_image_company_name_preserved(self) -> None:
        """Logo.company reflects the company argument passed to fetch_logos."""
        self._mock_get(_HTML_OG_IMAGE)
        logos = self.scraper.fetch_logos("Stripe, Inc.", self.url)

        assert logos[0].company == "Stripe, Inc."

    def test_og_image_url_property_also_accepted(self) -> None:
        """og:image:url is treated as equivalent to og:image."""
        self._mock_get(_HTML_OG_IMAGE_URL)
        logos = self.scraper.fetch_logos("Stripe", self.url)

        assert len(logos) == 1
        assert logos[0].url == "https://media.licdn.com/dms/image/alt-logo.jpg"

    def test_og_image_duplicate_urls_collapsed(self) -> None:
        """Same URL in og:image and og:image:url yields a single Logo."""
        self._mock_get(_HTML_OG_IMAGE_DUPLICATE)
        logos = self.scraper.fetch_logos("Stripe", self.url)

        assert len(logos) == 1

    def test_page_with_no_logo_returns_empty_list(self) -> None:
        """Page that has images but none hinting at a logo → empty list."""
        self._mock_get(_HTML_NO_LOGO)
        logos = self.scraper.fetch_logos("Stripe", self.url)

        assert logos == []


# ---------------------------------------------------------------------------
# 2. JSON-LD extraction
# ---------------------------------------------------------------------------

class TestJsonLdExtraction:
    """LinkedIn pages that expose logo data inside JSON-LD structured data."""

    def setup_method(self) -> None:
        self.scraper = LinkedInScraper(timeout=5)
        self.url = "https://www.linkedin.com/company/stripe"

    def _mock_get(self, html: str) -> None:
        resp = _make_response(text=html, url=self.url)
        self.scraper._session.get = MagicMock(return_value=resp)

    def test_json_ld_logo_string_key(self) -> None:
        """Organization JSON-LD with a plain string 'logo' key is extracted."""
        self._mock_get(_HTML_JSON_LD_LOGO)
        logos = self.scraper.fetch_logos("Stripe", self.url)

        assert any(
            "jsonld-logo.png" in logo.url for logo in logos
        ), f"Expected jsonld-logo.png in {[logo.url for logo in logos]}"

    def test_json_ld_logo_nested_image_object(self) -> None:
        """Nested ImageObject with a 'url' key inside 'logo' is extracted."""
        self._mock_get(_HTML_JSON_LD_IMAGE_OBJECT)
        logos = self.scraper.fetch_logos("Stripe", self.url)

        assert any("nested-logo.png" in logo.url for logo in logos)

    def test_json_ld_invalid_json_does_not_raise(self) -> None:
        """Malformed JSON-LD block is silently skipped — no exception propagated."""
        self._mock_get(_HTML_JSON_LD_INVALID)
        logos = self.scraper.fetch_logos("Stripe", self.url)  # must not raise
        assert isinstance(logos, list)

    def test_json_ld_non_http_strings_excluded(self) -> None:
        """Values that don't start with 'http' are not returned as logo URLs."""
        html = """\
<script type="application/ld+json">
{"logo": "data:image/png;base64,ABC123=="}
</script>"""
        resp = _make_response(text=html, url=self.url)
        self.scraper._session.get = MagicMock(return_value=resp)

        logos = self.scraper.fetch_logos("Stripe", self.url)

        assert all(logo.url.startswith("http") for logo in logos)


# ---------------------------------------------------------------------------
# 3. Blocked responses (403, 999, authwall redirect)
# ---------------------------------------------------------------------------

class TestBlockedResponses:
    """LinkedIn's various anti-scraping responses must all yield an empty list
    without raising an exception to the caller."""

    def setup_method(self) -> None:
        self.scraper = LinkedInScraper(timeout=5)
        self.url = "https://www.linkedin.com/company/stripe"

    def _mock_get_status(self, status: int, final_url: str | None = None) -> None:
        resp = _make_response(status_code=status, url=final_url or self.url)
        self.scraper._session.get = MagicMock(return_value=resp)

    def test_http_403_returns_empty_list(self) -> None:
        """HTTP 403 Forbidden → empty list, no exception."""
        self._mock_get_status(403)
        result = self.scraper.fetch_logos("Stripe", self.url)
        assert result == []

    def test_http_999_returns_empty_list(self) -> None:
        """HTTP 999 (LinkedIn-specific rate-limit code) → empty list, no exception."""
        self._mock_get_status(999)
        result = self.scraper.fetch_logos("Stripe", self.url)
        assert result == []

    def test_authwall_redirect_returns_empty_list(self) -> None:
        """Redirect to linkedin.com/authwall → empty list, no exception."""
        self._mock_get_status(
            200, final_url="https://www.linkedin.com/authwall?trk=bf&trkInfo=xyz"
        )
        result = self.scraper.fetch_logos("Stripe", self.url)
        assert result == []

    def test_login_redirect_returns_empty_list(self) -> None:
        """Redirect to linkedin.com/login → empty list, no exception."""
        self._mock_get_status(
            200, final_url="https://www.linkedin.com/login?session_redirect=..."
        )
        result = self.scraper.fetch_logos("Stripe", self.url)
        assert result == []

    def test_403_emits_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A warning is logged when LinkedIn blocks, so operators can monitor it."""
        import logging

        self._mock_get_status(403)
        with caplog.at_level(logging.WARNING, logger="logo_scraper.scraper.linkedin"):
            self.scraper.fetch_logos("Stripe", self.url)

        assert any("blocked" in record.message.lower() for record in caplog.records)


# ---------------------------------------------------------------------------
# 4. Invalid / unreachable URLs
# ---------------------------------------------------------------------------

class TestInvalidUrls:
    """Unreachable hosts, connection errors and timeouts must not raise."""

    def setup_method(self) -> None:
        self.scraper = LinkedInScraper(timeout=5)

    def test_connection_error_returns_empty_list(self) -> None:
        """DNS / connection failure → empty list, no exception."""
        self.scraper._session.get = MagicMock(
            side_effect=requests.ConnectionError("Name resolution failed")
        )
        result = self.scraper.fetch_logos(
            "Stripe", "https://www.linkedin.com/company/stripe"
        )
        assert result == []

    def test_timeout_returns_empty_list(self) -> None:
        """Read timeout → empty list, no exception."""
        self.scraper._session.get = MagicMock(
            side_effect=requests.Timeout("timed out")
        )
        result = self.scraper.fetch_logos(
            "Stripe", "https://www.linkedin.com/company/stripe"
        )
        assert result == []

    def test_ssl_error_returns_empty_list(self) -> None:
        """SSL certificate error → empty list, no exception."""
        self.scraper._session.get = MagicMock(
            side_effect=requests.exceptions.SSLError("certificate verify failed")
        )
        result = self.scraper.fetch_logos(
            "Stripe", "https://www.linkedin.com/company/stripe"
        )
        assert result == []

    def test_malformed_url_returns_empty_list(self) -> None:
        """Completely malformed URL that requests cannot parse → empty list."""
        self.scraper._session.get = MagicMock(
            side_effect=requests.exceptions.InvalidURL("Invalid URL")
        )
        result = self.scraper.fetch_logos("Stripe", "not-a-url-at-all")
        assert result == []


# ---------------------------------------------------------------------------
# 5. _get_html internals
# ---------------------------------------------------------------------------

class TestGetHtml:
    """Unit tests for the _get_html helper in isolation."""

    def setup_method(self) -> None:
        self.scraper = LinkedInScraper(timeout=5)

    def test_200_returns_beautifulsoup(self) -> None:
        resp = _make_response(text="<html><body>ok</body></html>")
        self.scraper._session.get = MagicMock(return_value=resp)
        soup = self.scraper._get_html("https://www.linkedin.com/company/stripe")
        assert soup.find("body") is not None

    def test_403_raises_linked_in_blocked(self) -> None:
        resp = _make_response(status_code=403)
        self.scraper._session.get = MagicMock(return_value=resp)
        with pytest.raises(_LinkedInBlocked):
            self.scraper._get_html("https://www.linkedin.com/company/stripe")

    def test_999_raises_linked_in_blocked(self) -> None:
        resp = _make_response(status_code=999)
        self.scraper._session.get = MagicMock(return_value=resp)
        with pytest.raises(_LinkedInBlocked):
            self.scraper._get_html("https://www.linkedin.com/company/stripe")

    def test_authwall_redirect_raises_linked_in_blocked(self) -> None:
        resp = _make_response(url="https://www.linkedin.com/authwall?trk=xyz")
        self.scraper._session.get = MagicMock(return_value=resp)
        with pytest.raises(_LinkedInBlocked, match="authwall"):
            self.scraper._get_html("https://www.linkedin.com/company/stripe")

    def test_sleep_is_called_before_request(self) -> None:
        """The polite delay must happen before the GET, not after."""
        call_order: list[str] = []

        with patch("logo_scraper.scraper.linkedin.time.sleep", side_effect=lambda _: call_order.append("sleep")):
            resp = _make_response(text="<html></html>")
            self.scraper._session.get = MagicMock(
                side_effect=lambda *a, **kw: call_order.append("get") or resp
            )
            self.scraper._get_html("https://www.linkedin.com/company/stripe")

        assert call_order == ["sleep", "get"]


# ---------------------------------------------------------------------------
# 6. scrape_linkedin_logo — standalone function (integration-style)
# ---------------------------------------------------------------------------

class TestScrapeLinkedinLogoFunction:
    """Tests for the public scrape_linkedin_logo() convenience function.

    File I/O is performed against a real tmp_path; only HTTP is mocked.
    """

    _URL = "https://www.linkedin.com/company/stripe"

    def _patch_session_get(self, scraper_instance: LinkedInScraper, html: str) -> None:
        resp = _make_response(text=html, url=self._URL)
        scraper_instance._session.get = MagicMock(return_value=resp)

    def test_blocked_response_returns_empty_list(self, tmp_path: Path) -> None:
        """403 during page fetch → scrape_linkedin_logo returns []."""
        with patch(
            "logo_scraper.scraper.linkedin.LinkedInScraper.fetch_logos",
            return_value=[],
        ):
            result = scrape_linkedin_logo(self._URL, tmp_path)

        assert result == []
        assert list(tmp_path.iterdir()) == []

    def test_slug_extracted_from_url_path(self, tmp_path: Path) -> None:
        """Company slug is derived from the last path segment of the LinkedIn URL."""
        captured: dict = {}

        def spy(self_inner, company, linkedin_url):
            captured["company"] = company
            return []

        with patch.object(LinkedInScraper, "fetch_logos", spy):
            scrape_linkedin_logo(
                "https://www.linkedin.com/company/acme-corp", tmp_path
            )

        assert captured["company"] == "acme-corp"

    def test_invalid_image_bytes_not_saved(self, tmp_path: Path) -> None:
        """If a candidate URL returns non-image bytes, no file is persisted."""
        from logo_scraper.models import Logo

        fake_logo = Logo(
            company="stripe",
            source=LogoSource.LINKEDIN,
            url="https://media.licdn.com/dms/image/fake.png",
        )

        bad_response = MagicMock()
        bad_response.status_code = 200
        bad_response.raise_for_status = MagicMock()
        bad_response.content = b"this is not an image"

        with (
            patch.object(LinkedInScraper, "fetch_logos", return_value=[fake_logo]),
            patch("logo_scraper.scraper.linkedin.requests.get", return_value=bad_response),
        ):
            result = scrape_linkedin_logo(self._URL, tmp_path)

        assert result == []
        assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# 7. _walk_json helper — edge cases
# ---------------------------------------------------------------------------

class TestWalkJson:
    def test_finds_logo_string_key(self) -> None:
        data = {"@type": "Organization", "logo": "https://example.com/logo.png"}
        assert "https://example.com/logo.png" in _walk_json(data)

    def test_finds_nested_image_key(self) -> None:
        data = {"org": {"image": "https://example.com/img.png"}}
        assert "https://example.com/img.png" in _walk_json(data)

    def test_traverses_list_of_objects(self) -> None:
        data = [
            {"logo": "https://a.com/logo.png"},
            {"logo": "https://b.com/logo.png"},
        ]
        results = _walk_json(data)
        assert "https://a.com/logo.png" in results
        assert "https://b.com/logo.png" in results

    def test_ignores_non_string_values(self) -> None:
        data = {"logo": 42, "image": None, "url": ["list"]}
        assert _walk_json(data) == []

    def test_empty_containers(self) -> None:
        assert _walk_json({}) == []
        assert _walk_json([]) == []

    def test_deeply_nested_structure(self) -> None:
        data = {"a": {"b": {"c": {"logo": "https://deep.example.com/logo.png"}}}}
        assert "https://deep.example.com/logo.png" in _walk_json(data)
