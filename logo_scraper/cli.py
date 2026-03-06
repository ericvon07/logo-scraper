"""Command-line interface for logo-scraper."""

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logo-scraper",
        description="Fetch and download company logos from multiple sources.",
    )

    parser.add_argument("company", help="Company name (used for output filenames).")
    parser.add_argument("domain", help='Company domain, e.g. "stripe.com".')

    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("logos"),
        help="Directory where logos will be saved (default: ./logos).",
    )
    parser.add_argument(
        "--sources",
        "-s",
        nargs="+",
        choices=["website", "logodev", "linkedin"],
        default=["website", "logodev", "linkedin"],
        help="Sources to query (default: all).",
    )
    parser.add_argument(
        "--linkedin-slug",
        help="LinkedIn company slug (required when 'linkedin' is in --sources).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="HTTP request timeout in seconds (default: 10).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CLI.

    Returns:
        Exit code (0 = success, non-zero = error).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if "linkedin" in args.sources and not args.linkedin_slug:
        parser.error("--linkedin-slug is required when 'linkedin' is in --sources.")

    raise NotImplementedError("CLI execution not yet implemented.")


if __name__ == "__main__":
    sys.exit(main())
