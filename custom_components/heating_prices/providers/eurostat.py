"""Household natural gas prices from Eurostat.

Eurostat publishes average household gas prices (all taxes included) twice a
year (dataset nrg_pc_202). To show a current value, the latest half-year price
is carried forward with the monthly consumer price index for gas
(dataset prc_hicp_minr, COICOP 04.5.2.1). The result is an estimate and is
marked as such. Eurostat data is licensed under CC BY 4.0.
"""

from __future__ import annotations

from datetime import date
from statistics import fmean
from typing import Any
from urllib.parse import urlencode

from . import ParseError, PriceSeries

API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
INFO_URL = "https://ec.europa.eu/eurostat/databrowser/view/nrg_pc_202/default/table"
SOURCE = "Eurostat"
ATTRIBUTION = "Source: Eurostat (nrg_pc_202, prc_hicp_minr), CC BY 4.0"

# Annual consumption bands of nrg_pc_202.
BAND_CODES = {"d1": "GJ_LT20", "d2": "GJ20-199", "d3": "GJ_GE200"}

# Eurostat uses EL for Greece, the Oil Bulletin uses GR.
_GEO = {"GR": "EL"}

_HICP_MONTHS = 36
_SEMESTERS = 6
_CHART_MONTHS = 24


def _geo(country: str) -> str:
    return _GEO.get(country, country)


def gas_price_url(country: str, band: str) -> str:
    """URL for the half-yearly household gas prices in EUR/kWh."""
    query = {
        "geo": _geo(country),
        # v0.1.0 stored the band in upper case.
        "nrg_cons": BAND_CODES[band.lower()],
        "unit": "KWH",
        "tax": "I_TAX",
        "currency": "EUR",
        "lastTimePeriod": _SEMESTERS,
    }
    return f"{API}nrg_pc_202?{urlencode(query)}"


def gas_index_url(country: str) -> str:
    """URL for the monthly HICP index of natural gas (2025 = 100)."""
    query = {
        "geo": _geo(country),
        "coicop18": "CP04521",
        "unit": "I25",
        "lastTimePeriod": _HICP_MONTHS,
    }
    return f"{API}prc_hicp_minr?{urlencode(query)}"


def parse_time_series(data: dict[str, Any]) -> list[tuple[str, float]]:
    """Return (time label, value) pairs of a single-series JSON-stat dataset."""
    try:
        if any(size != 1 for size in data["size"][:-1]):
            raise ParseError("Expected exactly one series")
        time_index: dict[str, int] = data["dimension"]["time"]["category"]["index"]
        values: dict[str, float | None] = data["value"]
    except (KeyError, TypeError) as err:
        raise ParseError("Unexpected JSON-stat structure") from err
    series = [
        (label, float(values[str(position)]))
        for label, position in time_index.items()
        if values.get(str(position)) is not None
    ]
    return sorted(series)


def _semester_months(label: str) -> list[str]:
    """Return the month labels of a half-year label such as "2026-S1"."""
    year, half = label.split("-S")
    months = range(1, 7) if half == "1" else range(7, 13)
    return [f"{year}-{month:02d}" for month in months]


def _month_date(label: str) -> date:
    year, month = label.split("-")
    return date(int(year), int(month), 1)


def build_gas_series(
    prices: dict[str, Any], index: dict[str, Any] | None
) -> PriceSeries:
    """Combine half-year prices and the monthly index into ct/kWh per month."""
    semesters = parse_time_series(prices)
    if not semesters:
        raise ParseError("No gas prices for this country and band")
    official_label, official_eur = semesters[-1]
    official_ct = official_eur * 100
    extra: dict[str, object] = {
        "official_price": round(official_ct, 2),
        "official_period": official_label,
    }

    monthly = dict(parse_time_series(index)) if index else {}
    base_values = [
        monthly[month] for month in _semester_months(official_label) if month in monthly
    ]

    if base_values:
        # Scale every month by its index relative to the official half-year.
        base = fmean(base_values)
        points = [
            (_month_date(month), round(official_ct * value / base, 2))
            for month, value in sorted(monthly.items())
        ][-_CHART_MONTHS:]
        estimated = True
    else:
        points = [
            (_month_date(_semester_months(label)[0]), round(value * 100, 2))
            for label, value in semesters
        ]
        estimated = False

    return PriceSeries(
        points=points,
        source=SOURCE,
        source_url=INFO_URL,
        attribution=ATTRIBUTION,
        estimated=estimated,
        extra=extra,
    )
