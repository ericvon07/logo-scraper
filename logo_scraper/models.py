"""Dataclasses for Logo and ScrapeResult."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class LogoSource(str, Enum):
    WEBSITE = "website"
    LOGODEV = "logodev"
    LINKEDIN = "linkedin"


@dataclass
class Logo:
    """Represents a downloaded company logo."""

    company: str
    source: LogoSource
    url: str
    local_path: Path | None = None
    width: int | None = None
    height: int | None = None
    format: str | None = None  # e.g. "PNG", "SVG", "JPEG"

    def is_downloaded(self) -> bool:
        """Return True if the logo has been saved locally."""
        return self.local_path is not None and self.local_path.exists()


@dataclass
class ScrapeResult:
    """Aggregated result of a logo scraping operation for one company."""

    company: str
    domain: str
    logos: list[Logo] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Return True if at least one logo was found."""
        return len(self.logos) > 0

    def best_logo(self) -> Logo | None:
        """Return the first available logo, preferring downloaded ones."""
        downloaded = [logo for logo in self.logos if logo.is_downloaded()]
        return downloaded[0] if downloaded else (self.logos[0] if self.logos else None)
