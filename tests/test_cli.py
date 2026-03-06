"""Tests for logo_scraper.cli."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from logo_scraper.cli import _slugify, build_parser, main
from logo_scraper.models import Logo, LogoSource, ScrapeResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_result(company: str, domain: str, n_logos: int = 1, source: LogoSource = LogoSource.LOGODEV) -> ScrapeResult:
    logos = [
        Logo(company=company, source=source, url=f"https://example.com/{i}.png")
        for i in range(n_logos)
    ]
    return ScrapeResult(company=company, domain=domain, logos=logos)


def _empty_result(company: str, domain: str) -> ScrapeResult:
    return ScrapeResult(company=company, domain=domain)


# ---------------------------------------------------------------------------
# _slugify
# ---------------------------------------------------------------------------

class TestSlugify:
    def test_lowercase(self):
        assert _slugify("Nubank") == "nubank"

    def test_spaces_become_underscores(self):
        assert _slugify("Patria Investments") == "patria_investments"

    def test_special_chars_replaced(self):
        slug = _slugify('my:company"name')
        assert '"' not in slug
        assert ":" not in slug

    def test_already_clean(self):
        assert _slugify("vercel") == "vercel"


# ---------------------------------------------------------------------------
# build_parser — argument validation
# ---------------------------------------------------------------------------

class TestBuildParser:
    def test_name_and_from_file_are_mutually_exclusive(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--name", "Nubank", "--from-file", "file.json"])

    def test_name_or_from_file_required(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_name_accepted(self):
        args = build_parser().parse_args(["--name", "Nubank"])
        assert args.name == "Nubank"
        assert args.from_file is None

    def test_from_file_accepted(self):
        args = build_parser().parse_args(["--from-file", "companies.json"])
        assert args.from_file == "companies.json"
        assert args.name is None

    def test_output_default(self):
        args = build_parser().parse_args(["--name", "X"])
        assert args.output == "./output"

    def test_output_custom(self):
        args = build_parser().parse_args(["--name", "X", "--output", "/tmp/logos"])
        assert args.output == "/tmp/logos"

    def test_url_optional_in_single_mode(self):
        args = build_parser().parse_args(["--name", "X", "--url", "https://x.com"])
        assert args.url == "https://x.com"

    def test_linkedin_optional(self):
        args = build_parser().parse_args(["--name", "X", "--linkedin", "https://linkedin.com/company/x"])
        assert args.linkedin == "https://linkedin.com/company/x"


# ---------------------------------------------------------------------------
# Single mode (--name)
# ---------------------------------------------------------------------------

class TestSingleMode:
    def test_success_returns_exit_code_0(self, capsys):
        result = _make_result("Nubank", "nubank.com.br")
        with patch("logo_scraper.cli.fetch_logos", return_value=result):
            code = main(["--name", "Nubank", "--url", "https://nubank.com.br"])
        assert code == 0

    def test_no_logos_returns_exit_code_1(self, capsys):
        result = _empty_result("Ghost", "ghost.com")
        with patch("logo_scraper.cli.fetch_logos", return_value=result):
            code = main(["--name", "Ghost"])
        assert code == 1

    def test_summary_shows_company_name(self, capsys):
        result = _make_result("Stripe", "stripe.com")
        with patch("logo_scraper.cli.fetch_logos", return_value=result):
            main(["--name", "Stripe", "--url", "https://stripe.com"])
        out = capsys.readouterr().out
        assert "Stripe" in out

    def test_summary_shows_logo_count(self, capsys):
        result = _make_result("Stripe", "stripe.com", n_logos=2)
        with patch("logo_scraper.cli.fetch_logos", return_value=result):
            main(["--name", "Stripe"])
        out = capsys.readouterr().out
        assert "2" in out

    def test_summary_shows_source(self, capsys):
        result = _make_result("Stripe", "stripe.com", source=LogoSource.WEBSITE)
        with patch("logo_scraper.cli.fetch_logos", return_value=result):
            main(["--name", "Stripe"])
        out = capsys.readouterr().out
        assert "website" in out

    def test_fetch_logos_called_with_correct_args(self):
        result = _make_result("Nubank", "nubank.com.br")
        with patch("logo_scraper.cli.fetch_logos", return_value=result) as mock_fetch:
            main([
                "--name", "Nubank",
                "--url", "https://nubank.com.br",
                "--linkedin", "https://linkedin.com/company/nubank",
                "--output", "/tmp/out",
            ])
        mock_fetch.assert_called_once_with(
            company_name="Nubank",
            website_url="https://nubank.com.br",
            linkedin_url="https://linkedin.com/company/nubank",
            output_dir="/tmp/out",
            logodev_api_key=None,
        )

    def test_no_logos_prints_error_messages(self, capsys):
        result = _empty_result("Ghost", "ghost.com")
        result.errors = ["logodev: key missing", "website: timeout"]
        with patch("logo_scraper.cli.fetch_logos", return_value=result):
            main(["--name", "Ghost"])
        out = capsys.readouterr().out
        assert "logodev: key missing" in out
        assert "website: timeout" in out

    def test_downloaded_logo_shows_local_path(self, tmp_path, capsys):
        logo_file = tmp_path / "logo.png"
        logo_file.write_bytes(b"PNG")
        logo = Logo(
            company="X",
            source=LogoSource.LOGODEV,
            url="https://example.com/logo.png",
            local_path=logo_file,
            width=200,
            height=200,
            format="PNG",
        )
        result = ScrapeResult(company="X", domain="x.com", logos=[logo])
        with patch("logo_scraper.cli.fetch_logos", return_value=result):
            main(["--name", "X"])
        out = capsys.readouterr().out
        assert str(logo_file) in out


# ---------------------------------------------------------------------------
# Batch mode (--from-file)
# ---------------------------------------------------------------------------

class TestBatchMode:
    def _write_json(self, tmp_path: Path, data: list) -> Path:
        f = tmp_path / "companies.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        return f

    def test_returns_0_when_all_companies_have_logos(self, tmp_path, capsys):
        companies = [
            {"name": "Nubank", "url": "https://nubank.com.br", "linkedin": None},
            {"name": "Stripe", "url": "https://stripe.com", "linkedin": None},
        ]
        f = self._write_json(tmp_path, companies)
        results = [
            _make_result("Nubank", "nubank.com.br"),
            _make_result("Stripe", "stripe.com"),
        ]
        with patch("logo_scraper.cli.fetch_logos", side_effect=results):
            code = main(["--from-file", str(f), "--output", str(tmp_path)])
        assert code == 0

    def test_returns_1_when_some_companies_have_no_logos(self, tmp_path, capsys):
        companies = [
            {"name": "Nubank", "url": "https://nubank.com.br", "linkedin": None},
            {"name": "Ghost", "url": None, "linkedin": None},
        ]
        f = self._write_json(tmp_path, companies)
        results = [
            _make_result("Nubank", "nubank.com.br"),
            _empty_result("Ghost", "ghost.com"),
        ]
        with patch("logo_scraper.cli.fetch_logos", side_effect=results):
            code = main(["--from-file", str(f), "--output", str(tmp_path)])
        assert code == 1

    def test_returns_2_for_missing_file(self, tmp_path, capsys):
        code = main(["--from-file", str(tmp_path / "missing.json"), "--output", str(tmp_path)])
        assert code == 2

    def test_returns_2_for_invalid_json(self, tmp_path, capsys):
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        code = main(["--from-file", str(bad), "--output", str(tmp_path)])
        assert code == 2

    def test_returns_2_for_non_list_json(self, tmp_path, capsys):
        bad = tmp_path / "bad.json"
        bad.write_text('{"name": "Nubank"}', encoding="utf-8")
        code = main(["--from-file", str(bad), "--output", str(tmp_path)])
        assert code == 2

    def test_each_company_gets_own_subdirectory(self, tmp_path):
        companies = [
            {"name": "Nubank", "url": "https://nubank.com.br", "linkedin": None},
            {"name": "Patria Investments", "url": "https://patria.com", "linkedin": None},
        ]
        f = self._write_json(tmp_path, companies)
        calls: list[dict] = []

        def capture(**kwargs):
            calls.append(kwargs)
            return _make_result(kwargs["company_name"], "x.com")

        with patch("logo_scraper.cli.fetch_logos", side_effect=capture):
            main(["--from-file", str(f), "--output", str(tmp_path)])

        assert calls[0]["output_dir"] == str(tmp_path / "nubank")
        assert calls[1]["output_dir"] == str(tmp_path / "patria_investments")

    def test_batch_calls_fetch_logos_for_each_company(self, tmp_path):
        companies = [
            {"name": "A", "url": "https://a.com", "linkedin": "https://linkedin.com/company/a"},
            {"name": "B", "url": None, "linkedin": None},
        ]
        f = self._write_json(tmp_path, companies)
        with patch("logo_scraper.cli.fetch_logos", return_value=_empty_result("x", "x.com")) as mock:
            main(["--from-file", str(f), "--output", str(tmp_path)])
        assert mock.call_count == 2

    def test_batch_passes_url_and_linkedin(self, tmp_path):
        companies = [{"name": "Nubank", "url": "https://nubank.com.br", "linkedin": "https://linkedin.com/company/nubank"}]
        f = self._write_json(tmp_path, companies)
        with patch("logo_scraper.cli.fetch_logos", return_value=_make_result("Nubank", "nubank.com.br")) as mock:
            main(["--from-file", str(f), "--output", str(tmp_path)])
        _, kwargs = mock.call_args
        assert kwargs["website_url"] == "https://nubank.com.br"
        assert kwargs["linkedin_url"] == "https://linkedin.com/company/nubank"

    def test_batch_handles_null_url_and_linkedin(self, tmp_path):
        companies = [{"name": "X", "url": None, "linkedin": None}]
        f = self._write_json(tmp_path, companies)
        with patch("logo_scraper.cli.fetch_logos", return_value=_empty_result("X", "x.com")) as mock:
            main(["--from-file", str(f), "--output", str(tmp_path)])
        _, kwargs = mock.call_args
        assert kwargs["website_url"] is None
        assert kwargs["linkedin_url"] is None

    def test_batch_skips_entries_without_name(self, tmp_path, capsys):
        companies = [
            {"url": "https://noname.com"},
            {"name": "Valid", "url": "https://valid.com", "linkedin": None},
        ]
        f = self._write_json(tmp_path, companies)
        with patch("logo_scraper.cli.fetch_logos", return_value=_make_result("Valid", "valid.com")) as mock:
            main(["--from-file", str(f), "--output", str(tmp_path)])
        assert mock.call_count == 1

    def test_batch_summary_table_printed(self, tmp_path, capsys):
        companies = [{"name": "Nubank", "url": "https://nubank.com.br", "linkedin": None}]
        f = self._write_json(tmp_path, companies)
        with patch("logo_scraper.cli.fetch_logos", return_value=_make_result("Nubank", "nubank.com.br")):
            main(["--from-file", str(f), "--output", str(tmp_path)])
        out = capsys.readouterr().out
        assert "Nubank" in out
        assert "Company" in out
        assert "Logos" in out
        assert "Sources" in out

    def test_batch_summary_shows_totals(self, tmp_path, capsys):
        companies = [
            {"name": "A", "url": "https://a.com", "linkedin": None},
            {"name": "B", "url": "https://b.com", "linkedin": None},
        ]
        f = self._write_json(tmp_path, companies)
        results = [_make_result("A", "a.com"), _empty_result("B", "b.com")]
        with patch("logo_scraper.cli.fetch_logos", side_effect=results):
            main(["--from-file", str(f), "--output", str(tmp_path)])
        out = capsys.readouterr().out
        assert "1/2" in out
