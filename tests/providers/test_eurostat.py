"""Tests for the Eurostat gas price parser."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from heating_prices.providers import ParseError
from heating_prices.providers.eurostat import (
    build_gas_series,
    gas_index_url,
    gas_price_url,
    parse_time_series,
)


def jsonstat(values: dict[str, float | None]) -> dict[str, Any]:
    """A single-series JSON-stat 2.0 dataset like the Eurostat API returns."""
    labels = list(values)
    return {
        "version": "2.0",
        "class": "dataset",
        "id": ["freq", "geo", "time"],
        "size": [1, 1, len(labels)],
        "value": {str(i): v for i, v in enumerate(values.values()) if v is not None},
        "dimension": {
            "freq": {"category": {"index": {"S": 0}}},
            "geo": {"category": {"index": {"DE": 0}}},
            "time": {
                "category": {"index": {label: i for i, label in enumerate(labels)}}
            },
        },
    }


SEMESTERS = jsonstat({"2025-S1": 0.1216, "2025-S2": 0.1223, "2026-S1": 0.1156})
INDEX = jsonstat(
    {
        "2025-12": 99.94, "2026-01": 97.62, "2026-02": 97.38, "2026-03": 97.23,
        "2026-04": 97.14, "2026-05": 97.14, "2026-06": 97.07, "2026-07": 97.11,
        "2026-08": 97.13, "2026-09": 96.09,
    }
)  # fmt: skip


def test_urls() -> None:
    """Greece is "EL" at Eurostat and bands map to consumption codes."""
    assert "geo=EL" in gas_price_url("GR", "D2")
    assert "nrg_cons=GJ20-199" in gas_price_url("DE", "D2")
    assert "nrg_cons=GJ_LT20" in gas_price_url("DE", "D1")
    assert "coicop18=CP04521" in gas_index_url("DE")


def test_parse_time_series_skips_missing() -> None:
    """Positions without a value are left out."""
    data = jsonstat({"2025-S2": 0.12, "2026-S1": None})
    assert parse_time_series(data) == [("2025-S2", 0.12)]


def test_parse_time_series_rejects_other_shapes() -> None:
    """Unexpected payloads raise a parse error."""
    with pytest.raises(ParseError):
        parse_time_series({"error": "bad request"})


def test_estimate_with_index() -> None:
    """The latest half-year price is carried forward with the index."""
    series = build_gas_series(SEMESTERS, INDEX)
    assert series.estimated
    assert series.extra == {"official_price": 11.56, "official_period": "2026-S1"}
    base = (97.62 + 97.38 + 97.23 + 97.14 + 97.14 + 97.07) / 6
    assert series.latest == (date(2026, 9, 1), round(11.56 * 96.09 / base, 2))
    assert series.points[0][0] == date(2025, 12, 1)


def test_official_values_without_index() -> None:
    """Without the index the half-year prices are shown as they are."""
    series = build_gas_series(SEMESTERS, None)
    assert not series.estimated
    assert series.points == [
        (date(2025, 1, 1), 12.16),
        (date(2025, 7, 1), 12.23),
        (date(2026, 1, 1), 11.56),
    ]


def test_no_prices() -> None:
    """Countries without data raise a parse error."""
    with pytest.raises(ParseError):
        build_gas_series(jsonstat({"2026-S1": None}), INDEX)
