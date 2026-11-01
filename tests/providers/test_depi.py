"""Tests for the DEPI pellet price parser."""

from __future__ import annotations

from datetime import date

import pytest

from heating_prices.providers import ParseError, parse_decimal
from heating_prices.providers.depi import parse, select

from .conftest import FIXTURES

PAGE = (FIXTURES / "depi_page.html").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("464,61", 464.61),
        ("1.000,50", 1000.5),
        ("46,46\xa0Cent", 46.46),
        ("1234.5", 1234.5),
        ("\xa0", None),
        ("", None),
    ],
)
def test_parse_decimal(text: str, expected: float | None) -> None:
    """German and English number formats are understood."""
    assert parse_decimal(text) == expected


def test_parse_tables() -> None:
    """National and regional tables are recognised by their headings."""
    prices = parse(PAGE)
    assert set(prices.national) == {"6", "26"}
    six = prices.national["6"]
    assert len(six) == 22
    assert six[date(2025, 12, 1)] == 1000.5
    assert six[date(2026, 10, 1)] == 460.0
    assert date(2026, 11, 1) not in six
    assert prices.regional[("south", "3")][date(2026, 10, 1)] == 481.0
    assert prices.regional[("north_east", "6")][date(2026, 9, 1)] == 455.0


def test_select_national() -> None:
    """The nationwide series is used as is."""
    series = select(parse(PAGE), "national", "6")
    assert series.latest == (date(2026, 10, 1), 460.0)
    assert series.points[-2] == (date(2026, 9, 1), 450.0)
    assert series.extra["history_scope"] == "national"
    assert "DEPI" in series.attribution


def test_select_region_compares_regional_months() -> None:
    """A regional price is compared with the same region's previous month."""
    series = select(parse(PAGE), "south", "6")
    assert series.latest == (date(2026, 10, 1), 467.0)
    assert series.points[-2] == (date(2026, 9, 1), 458.0)
    # Older months come from the nationwide series.
    assert series.points[0] == (date(2025, 1, 1), 300.0)
    assert series.extra == {
        "region": "south",
        "quantity_t": 6,
        "history_scope": "national",
        "latest_period": "2026-10-01",
    }


def test_select_regional_only_quantity() -> None:
    """3 t exists per region only."""
    prices = parse(PAGE)
    assert select(prices, "central", "3").latest == (date(2026, 10, 1), 478.0)
    with pytest.raises(ParseError):
        select(prices, "national", "3")


def test_page_without_prices() -> None:
    """A redesigned page without the tables raises a parse error."""
    with pytest.raises(ParseError):
        parse("<html><body><p>Neue Seite</p></body></html>")
