"""Heating oil and LPG prices from the European Commission's Weekly Oil Bulletin.

Prices are consumer prices including all duties and taxes, published weekly per
EU member state in EUR per 1000 litres. Reproduction is authorised provided the
source is acknowledged.

The bulletin's LPG price is for LPG as a motor fuel (Autogas). LPG for heating
is taxed differently and has no official price, so the two can differ.
"""

from __future__ import annotations

from collections.abc import Iterable
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

HEATING_OIL = "heating_oil"
LPG = "lpg"

# How each product is named in the header of the latest and history workbooks.
_HEADER_MARKERS = {HEATING_OIL: ("heating gas oil", "heizöl"), LPG: ("lpg",)}
_COLUMN_SUFFIXES = {HEATING_OIL: "heating_oil", LPG: "LPG"}
_LITRES_PER_UNIT = 1000
_PER_LITRES = 100


def _to_price_per_100l(value: float) -> float:
    return round(value / _LITRES_PER_UNIT * _PER_LITRES, 2)


def _series(points: list[tuple[date, float]], product: str) -> PriceSeries:
    if not points:
        raise ParseError(f"No {product} prices found for this country")
    return PriceSeries(
        points=sorted(points),
        source=SOURCE,
        source_url=INFO_URL,
        attribution=ATTRIBUTION,
        extra={"price_basis": "motor_fuel"} if product == LPG else {},
    )


def parse_latest(
    content: bytes, country: str, product: str = HEATING_OIL
) -> PriceSeries:
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
            and any(marker in value.lower() for marker in _HEADER_MARKERS[product])
        ),
        None,
    )
    if column is None:
        raise ParseError(f"Column for {product} not found")

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
                return _series([(published, _to_price_per_100l(value))], product)
            break
    return _series([], product)


def parse_histories(
    content: bytes, country: str, products: Iterable[str]
) -> dict[str, PriceSeries]:
    """Parse the weekly history of several products in one pass.

    The workbook is large, so all products are read together. Products without
    any price for this country are left out of the result.
    """
    wanted = {f"{country}_price_with_tax_{_COLUMN_SUFFIXES[p]}": p for p in products}
    rows = iter_rows(content, sheet="Prices with taxes")
    header = next(rows, {})
    columns = {
        index: wanted[value] for index, value in header.items() if value in wanted
    }
    if not columns:
        raise ParseError(f"Columns {list(wanted)} not found")

    points: dict[str, list[tuple[date, float]]] = {p: [] for p in columns.values()}
    for row in rows:
        stamp = row.get(0)
        if not isinstance(stamp, float):
            continue
        for column, product in columns.items():
            value = row.get(column)
            if isinstance(value, float) and value > 0:
                points[product].append((excel_date(stamp), _to_price_per_100l(value)))

    series = {p: _series(values, p) for p, values in points.items() if values}
    if not series:
        raise ParseError(f"No prices found for {country}")
    return series


def parse_history(
    content: bytes, country: str, product: str = HEATING_OIL
) -> PriceSeries:
    """Parse the weekly history of one product (prices with taxes sheet)."""
    return parse_histories(content, country, [product])[product]
