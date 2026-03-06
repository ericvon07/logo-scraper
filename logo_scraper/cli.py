"""Command-line interface for logo-scraper."""

import argparse
import sys

from logo_scraper.orchestrator import fetch_logos


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logo-scraper",
        description="Fetch and download company logos from multiple sources.",
    )

    parser.add_argument("--name", required=True, help="Company name (e.g. 'Nubank').")
    parser.add_argument("--url", required=True, help="Company website URL (e.g. 'https://nubank.com.br').")
    parser.add_argument("--linkedin", default=None, help="LinkedIn company page URL (optional fallback).")
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


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CLI.

    Returns:
        Exit code (0 = success, 1 = no logos found).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    result = fetch_logos(
        company_name=args.name,
        website_url=args.url,
        linkedin_url=args.linkedin,
        output_dir=args.output,
        logodev_api_key=args.logodev_api_key,
    )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
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
        return 0
    else:
        print(f"No logos found for '{result.company}'.")
        if result.errors:
            for err in result.errors:
                print(f"  Error: {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
