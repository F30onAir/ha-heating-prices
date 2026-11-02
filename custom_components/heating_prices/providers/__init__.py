"""Price data sources.

Every module in this package only parses data that may be reused, because it is
openly licensed or its publisher allowed it, and has no Home Assistant imports, so
it can be tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


class ParseError(Exception):
    """Raised when a source document does not have the expected structure."""


@dataclass(slots=True)
class PriceSeries:
    """A price time series from one source, oldest point first."""

    points: list[tuple[date, float]]
    source: str
    source_url: str
    attribution: str
    estimated: bool = False
    extra: dict[str, object] = field(default_factory=dict)

    @property
    def latest(self) -> tuple[date, float]:
        """Return the most recent point."""
        return self.points[-1]


def parse_decimal(text: str) -> float | None:
    """Parse a number written in German or English notation.

    "1.234,56", "464,61" and "1234.56" are all accepted; blank cells return None.
    """
    cleaned = text.replace("\xa0", " ").strip().split(" ")[0]
    if not cleaned or not any(ch.isdigit() for ch in cleaned):
        return None
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None
