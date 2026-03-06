"""Command-line interface for logo-scraper."""

import argparse
import json
import sys
from pathlib import Path

from logo_scraper.models import ScrapeResult
from logo_scraper.orchestrator import fetch_logos
from logo_scraper.utils import sanitize_filename

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    """Convert a company name into a safe directory name."""
    return sanitize_filename(name.lower().replace(" ", "_"))


def _print_single_summary(result: ScrapeResult) -> None:
    """Print per-logo details for a single-company run."""
    if result.success:
        sources = sorted({logo.source.value for logo in result.logos})
        print(f"Found {len(result.logos)} logo(s) for '{result.company}' from: {', '.join(sources)}")
        for logo in result.logos:
            if logo.local_path:
                dims = f" ({logo.width}x{logo.height})" if logo.width and logo.height else ""
                fmt = f" [{logo.format}]" if logo.format else ""
                print(f"  {logo.local_path}{dims}{fmt}")
            else:
                print(f"  {logo.url}  (not downloaded)")
    else:
        print(f"No logos found for '{result.company}'.")
        for err in result.errors:
            print(f"  Error: {err}")


def _print_batch_summary(rows: list[dict]) -> None:
    """Print a formatted table summarising a batch run.

    Each row dict has keys: name, logos, sources.
    """
    col_name = max(len(r["name"]) for r in rows)
    col_name = max(col_name, len("Company"))
    col_logos = max(len(str(r["logos"])) for r in rows)
    col_logos = max(col_logos, len("Logos"))
    col_sources = max((len(r["sources"]) for r in rows), default=0)
    col_sources = max(col_sources, len("Sources"))

    sep = f"+{'-' * (col_name + 2)}+{'-' * (col_logos + 2)}+{'-' * (col_sources + 2)}+"
    header = f"| {'Company':<{col_name}} | {'Logos':<{col_logos}} | {'Sources':<{col_sources}} |"

    print()
    print(sep)
    print(header)
    print(sep)
    for row in rows:
        print(
            f"| {row['name']:<{col_name}} "
            f"| {str(row['logos']):<{col_logos}} "
            f"| {row['sources']:<{col_sources}} |"
        )
    print(sep)

    total = sum(r["logos"] for r in rows)
    found = sum(1 for r in rows if r["logos"] > 0)
    print(f"\n{found}/{len(rows)} companies with logos found  |  {total} logo(s) total")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logo-scraper",
        description="Fetch and download company logos from multiple sources.",
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--name", help="Company name (e.g. 'Nubank').")
    mode.add_argument(
        "--from-file",
        metavar="FILE",
        help="Path to a JSON file with a list of companies (batch mode).",
    )

    parser.add_argument("--url", default=None, help="Company website URL (single mode).")
    parser.add_argument("--linkedin", default=None, help="LinkedIn company page URL (optional).")
    parser.add_argument(
        "--output",
        default="./output",
        help="Directory where logos will be saved (default: ./output).",
    )
    parser.add_argument(
        "--logodev-api-key",
        default=None,
        help="logo.dev API key (falls back to LOGODEV_API_KEY env var).",
    )

    return parser


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def _run_single(args: argparse.Namespace) -> int:
    """Single-company mode."""
    result = fetch_logos(
        company_name=args.name,
        website_url=args.url,
        linkedin_url=args.linkedin,
        output_dir=args.output,
        logodev_api_key=args.logodev_api_key,
    )
    _print_single_summary(result)
    return 0 if result.success else 1


def _run_batch(args: argparse.Namespace) -> int:
    """Batch mode: read companies from a JSON file."""
    file_path = Path(args.from_file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        return 2

    try:
        companies = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {file_path}: {exc}", file=sys.stderr)
        return 2

    if not isinstance(companies, list):
        print("Error: JSON file must contain a top-level list of companies.", file=sys.stderr)
        return 2

    rows: list[dict] = []

    for entry in companies:
        name = entry.get("name", "").strip()
        if not name:
            print("Warning: skipping entry without 'name' field.", file=sys.stderr)
            continue

        company_output = str(Path(args.output) / _slugify(name))
        print(f"[{name}] scraping…", end=" ", flush=True)

        result = fetch_logos(
            company_name=name,
            website_url=entry.get("url"),
            linkedin_url=entry.get("linkedin"),
            output_dir=company_output,
            logodev_api_key=args.logodev_api_key,
        )

        sources_str = ", ".join(sorted({logo.source.value for logo in result.logos})) or "—"
        print(f"{len(result.logos)} logo(s) [{sources_str}]")

        rows.append({
            "name": name,
            "logos": len(result.logos),
            "sources": sources_str,
        })

    _print_batch_summary(rows)
    all_found = all(r["logos"] > 0 for r in rows)
    return 0 if all_found else 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Entry point for the CLI.

    Returns:
        Exit code (0 = success, 1 = no logos found, 2 = input error).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.from_file:
        return _run_batch(args)
    return _run_single(args)


if __name__ == "__main__":
    sys.exit(main())
