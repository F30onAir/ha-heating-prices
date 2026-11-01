"""Wood pellet prices for Germany from the Deutsches Pelletinstitut (DEPI).

DEPI publishes a monthly average price per tonne of ENplus A1 pellets
(loose, delivered within 50 km, all costs and VAT included), nationwide for
6 t and 26 t and for three regions for 3 t, 6 t and 26 t. The data may be used
free of charge with the source "Deutsches Pelletinstitut GmbH (DEPI)".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
import re

from . import ParseError, PriceSeries, parse_decimal

URL = "https://www.depi.de/pelletpreis-wirtschaftlichkeit/"
SOURCE = "DEPI Pelletpreis"
ATTRIBUTION = "Quelle: Deutsches Pelletinstitut GmbH (DEPI)"

REGION_LABELS = {"north_east": "nord/ost", "central": "mitte", "south": "süd"}

MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5,
    "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
    "november": 11, "dezember": 12,
}  # fmt: skip

_YEAR = re.compile(r"(20\d\d)")
_TONNES = re.compile(r"(\d+)\s*(?:t\b|tonnen)", re.IGNORECASE)
_MONTH_YEAR = re.compile(r"^([a-zäöü]+)\s+(20\d\d)$", re.IGNORECASE)


@dataclass(slots=True)
class _Table:
    heading: str
    rows: list[list[str]] = field(default_factory=list)


class _TableCollector(HTMLParser):
    """Collect every table with the heading text that precedes it."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[_Table] = []
        self._heading = ""
        self._heading_parts: list[str] | None = None
        self._table: _Table | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("h2", "h3", "h4") and self._table is None:
            self._heading_parts = []
        elif tag == "table":
            self._table = _Table(heading=self._heading)
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("h2", "h3", "h4") and self._heading_parts is not None:
            text = " ".join("".join(self._heading_parts).split())
            if text:
                self._heading = text
            self._heading_parts = None
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            self._table.rows.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)
        elif self._heading_parts is not None:
            self._heading_parts.append(data)


@dataclass(slots=True)
class PelletPrices:
    """All pellet price series found on the DEPI page, keyed by quantity in t."""

    national: dict[str, dict[date, float]] = field(default_factory=dict)
    regional: dict[tuple[str, str], dict[date, float]] = field(default_factory=dict)


def _month_start(month_name: str, year: int) -> date | None:
    month = MONTHS.get(month_name.strip().lower())
    return date(year, month, 1) if month else None


def _parse_national(table: _Table, prices: PelletPrices) -> None:
    quantity = _TONNES.search(table.heading)
    header = table.rows[0]
    years = [_YEAR.search(cell) for cell in header[1:]]
    if quantity is None or not years or not all(years):
        return
    series = prices.national.setdefault(quantity.group(1), {})
    for row in table.rows[1:]:
        if len(row) < 2:
            continue
        for match, cell in zip(years, row[1:], strict=False):
            when = _month_start(row[0], int(match.group(1)))
            value = parse_decimal(cell)
            if when and value:
                series[when] = value


def _parse_regional(table: _Table, prices: PelletPrices) -> None:
    header = [cell.lower() for cell in table.rows[0]]
    columns = {
        region: header.index(label)
        for region, label in REGION_LABELS.items()
        if label in header
    }
    quantity: str | None = None
    for row in table.rows[1:]:
        if not row:
            continue
        section = _TONNES.fullmatch(row[0].strip())
        if section:
            quantity = section.group(1)
            continue
        stamp = _MONTH_YEAR.match(row[0].strip())
        if quantity is None or stamp is None:
            continue
        when = _month_start(stamp.group(1), int(stamp.group(2)))
        if when is None:
            continue
        for region, column in columns.items():
            if column < len(row) and (value := parse_decimal(row[column])):
                prices.regional.setdefault((region, quantity), {})[when] = value


def parse(html: str) -> PelletPrices:
    """Parse every price table on the DEPI pellet price page."""
    collector = _TableCollector()
    collector.feed(html)
    prices = PelletPrices()
    for table in collector.tables:
        if not table.rows:
            continue
        header = " ".join(table.rows[0]).lower()
        if "nord/ost" in header:
            _parse_regional(table, prices)
        elif "tonnen" in table.heading.lower():
            _parse_national(table, prices)
    if not prices.national and not prices.regional:
        raise ParseError("No pellet price tables found")
    return prices


def select(prices: PelletPrices, region: str, quantity: str) -> PriceSeries:
    """Pick the series for a region and delivery quantity.

    The current price comes from the regional table when a region is chosen.
    Regional tables only cover the last few months, so the history shown in
    charts falls back to the nationwide series of the same quantity.
    """
    national_quantity = quantity if quantity in prices.national else "6"
    national = prices.national.get(national_quantity, {})

    if region == "national":
        current = prices.national.get(quantity, {})
        history_label = "national"
    else:
        current = prices.regional.get((region, quantity), {})
        history_label = "national" if len(current) < 6 else "regional"

    if not current:
        raise ParseError(f"No pellet price for {region} / {quantity} t")

    latest_date = max(current)
    source = current if history_label == "regional" else national
    history = {when: value for when, value in source.items() if when <= latest_date}
    # Regional months replace national ones so the change to the previous
    # month compares like with like.
    history.update(current)

    return PriceSeries(
        points=sorted(history.items()),
        source=SOURCE,
        source_url=URL,
        attribution=ATTRIBUTION,
        extra={
            "region": region,
            "quantity_t": int(quantity),
            "history_scope": history_label,
            "latest_period": latest_date.isoformat(),
        },
    )
