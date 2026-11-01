"""Heating oil prices from the European Commission's Weekly Oil Bulletin.

Prices are consumer prices including all duties and taxes, published weekly per
EU member state in EUR per 1000 litres. Reproduction is authorised provided the
source is acknowledged.
"""

from __future__ import annotations

from datetime import date

from . import ParseError, PriceSeries
from .xlsx import excel_date, iter_rows

LATEST_URL = (
    "https://energy.ec.europa.eu/document/download/"
    "264c2d0f-f161-4ea3-a777-78faae59bea0_en"
)
HISTORY_URL = (
    "https://energy.ec.europa.eu/document/download/"
    "906e60ca-8b6a-44e7-8589-652854d2fd3f_en"
)
INFO_URL = "https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en"
SOURCE = "EU Weekly Oil Bulletin"
ATTRIBUTION = "Source: European Commission, Weekly Oil Bulletin"

# Country names as they appear in the "latest prices" workbook.
COUNTRY_NAMES = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CY": "Cyprus",
    "CZ": "Czechia", "DE": "Germany", "DK": "Denmark", "EE": "Estonia",
    "ES": "Spain", "FI": "Finland", "FR": "France", "GR": "Greece",
    "HR": "Croatia", "HU": "Hungary", "IE": "Ireland", "IT": "Italy",
    "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MT": "Malta",
    "NL": "Netherlands", "PL": "Poland", "PT": "Portugal", "RO": "Romania",
    "SE": "Sweden", "SI": "Slovenia", "SK": "Slovakia",
}  # fmt: skip

_HEATING_OIL_MARKERS = ("heating gas oil", "heizöl")
_LITRES_PER_UNIT = 1000
_PER_LITRES = 100


def _to_price_per_100l(value: float) -> float:
    return round(value / _LITRES_PER_UNIT * _PER_LITRES, 2)


def _series(points: list[tuple[date, float]]) -> PriceSeries:
    if not points:
        raise ParseError("No heating oil prices found for this country")
    return PriceSeries(
        points=sorted(points),
        source=SOURCE,
        source_url=INFO_URL,
        attribution=ATTRIBUTION,
    )


def parse_latest(content: bytes, country: str) -> PriceSeries:
    """Parse the one-week "prices with taxes" workbook."""
    name = COUNTRY_NAMES.get(country)
    if name is None:
        raise ParseError(f"Country {country} is not part of the Oil Bulletin")

    rows = iter_rows(content)
    header = next(rows, {})
    column = next(
        (
            index
            for index, value in header.items()
            if isinstance(value, str)
            and any(marker in value.lower() for marker in _HEATING_OIL_MARKERS)
        ),
        None,
    )
    if column is None:
        raise ParseError("Heating oil column not found")

    units = next(rows, {})
    stamp = units.get(0)
    if not isinstance(stamp, float):
        raise ParseError("Publication date not found")
    published = excel_date(stamp)

    for row in rows:
        label = row.get(0)
        if isinstance(label, str) and label.strip() == name:
            value = row.get(column)
            if isinstance(value, float):
                return _series([(published, _to_price_per_100l(value))])
            break
    return _series([])


def parse_history(content: bytes, country: str) -> PriceSeries:
    """Parse the full weekly price history workbook (prices with taxes sheet)."""
    wanted = f"{country}_price_with_tax_heating_oil"
    rows = iter_rows(content, sheet="Prices with taxes")
    header = next(rows, {})
    column = next((index for index, value in header.items() if value == wanted), None)
    if column is None:
        raise ParseError(f"Column {wanted} not found")

    points: list[tuple[date, float]] = []
    for row in rows:
        stamp = row.get(0)
        value = row.get(column)
        if isinstance(stamp, float) and isinstance(value, float) and value > 0:
            points.append((excel_date(stamp), _to_price_per_100l(value)))
    return _series(points)
