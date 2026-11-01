"""Tests for the EU Weekly Oil Bulletin parser."""

from __future__ import annotations

from datetime import date

import pytest

from heating_prices.providers import ParseError
from heating_prices.providers.oil_bulletin import parse_history, parse_latest

from .conftest import FIXTURES
from .xlsx_builder import build_xlsx

LATEST = (FIXTURES / "oil_bulletin_latest.xlsx").read_bytes()


def test_latest_germany() -> None:
    """The real bulletin of 26 Oct 2026 lists 1750.10 EUR per 1000 L for Germany."""
    series = parse_latest(LATEST, "DE")
    assert series.points == [(date(2026, 10, 26), 175.01)]
    assert "European Commission" in series.attribution


@pytest.mark.parametrize(
    ("country", "price"), [("AT", 183.01), ("FR", 195.18), ("GR", 156.0)]
)
def test_latest_other_countries(country: str, price: float) -> None:
    """Other member states are read from the same sheet."""
    assert parse_latest(LATEST, country).latest[1] == price


def test_latest_country_without_heating_oil() -> None:
    """The Netherlands report no heating oil price."""
    with pytest.raises(ParseError):
        parse_latest(LATEST, "NL")


def test_latest_unknown_country() -> None:
    """Countries outside the bulletin are rejected."""
    with pytest.raises(ParseError):
        parse_latest(LATEST, "CH")


def test_not_a_workbook() -> None:
    """HTML error pages instead of the file raise a parse error."""
    with pytest.raises(ParseError):
        parse_latest(b"<html>maintenance</html>", "DE")


def test_history() -> None:
    """History rows are newest first in the file and come out oldest first."""
    content = build_xlsx(
        {
            "Prices with taxes": [
                [
                    "Consumer prices",
                    "CTR",
                    "EU_price_with_tax_heating_oil",
                    "CTR",
                    "DE_price_with_tax_heating_oil",
                ],
                [None, None, "Heating gas oil", None, "Heating gas oil"],
                ["Date", None, "1000 l", None, "1000 l"],
                [46321, "EU_", 1760.04, "DE_", 1750.1],
                [46314, "EU_", 1737.99, "DE_", None],
                [46307, "EU_", 1733.86, "DE_", 1698.0],
                ["Disclaimer", None, None, None, None],
            ],
            "Prices wo taxes": [["ignored"]],
        }
    )
    series = parse_history(content, "DE")
    assert series.points == [(date(2026, 10, 12), 169.8), (date(2026, 10, 26), 175.01)]


def test_history_missing_country() -> None:
    """A country without a column raises a parse error."""
    content = build_xlsx(
        {"Prices with taxes": [["x", "CTR", "EU_price_with_tax_heating_oil"]]}
    )
    with pytest.raises(ParseError):
        parse_history(content, "DE")
