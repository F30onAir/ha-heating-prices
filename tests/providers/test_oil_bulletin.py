"""Tests for the EU Weekly Oil Bulletin parser."""

from __future__ import annotations

from datetime import date

import pytest

from heating_prices.providers import ParseError
from heating_prices.providers.oil_bulletin import (
    HEATING_OIL,
    LPG,
    parse_histories,
    parse_history,
    parse_latest,
)

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


@pytest.mark.parametrize(
    ("country", "price"),
    [("BE", 107.1), ("FR", 104.08), ("IT", 78.9), ("NL", 99.71), ("PL", 81.3)],
)
def test_latest_lpg(country: str, price: float) -> None:
    """LPG is read from its own column and marked as a motor fuel price."""
    series = parse_latest(LATEST, country, LPG)
    assert series.latest[1] == price
    assert series.extra == {"price_basis": "motor_fuel"}


def test_latest_lpg_germany() -> None:
    """The real bulletin of 26 Oct 2026 lists 1130.25 EUR per 1000 L for Germany."""
    assert parse_latest(LATEST, "DE", LPG).points == [(date(2026, 10, 26), 113.02)]


@pytest.mark.parametrize("country", ["AT", "DK", "SE"])
def test_latest_country_without_lpg(country: str) -> None:
    """Some countries publish heating oil but no LPG price."""
    assert parse_latest(LATEST, country).latest[1] > 0
    with pytest.raises(ParseError):
        parse_latest(LATEST, country, LPG)


def test_heating_oil_is_not_marked() -> None:
    """Only LPG needs the motor fuel note."""
    assert parse_latest(LATEST, "DE").extra == {}


def _history_workbook() -> bytes:
    return build_xlsx(
        {
            "Prices with taxes": [
                [
                    "Consumer prices",
                    "CTR",
                    "DE_price_with_tax_heating_oil",
                    "DE_price_with_tax_LPG",
                    "AT_price_with_tax_heating_oil",
                    "AT_price_with_tax_LPG",
                ],
                [None, None, "Heating gas oil", "LPG", "Heating gas oil", "LPG"],
                ["Date", None, "1000 l", "1000 l", "1000 l", "1000 l"],
                [46321, "DE_", 1750.1, 1130.5, 1830.1, None],
                [46314, "DE_", 1700.0, None, 1800.0, None],
                [46307, "DE_", 1698.0, 1120.0, 1790.0, None],
            ],
        }
    )


def test_histories_reads_products_together() -> None:
    """Several products come from one pass over the workbook."""
    histories = parse_histories(_history_workbook(), "DE", [HEATING_OIL, LPG])
    assert histories[LPG].points == [
        (date(2026, 10, 12), 112.0),
        (date(2026, 10, 26), 113.05),
    ]
    assert histories[LPG].extra == {"price_basis": "motor_fuel"}
    assert len(histories[HEATING_OIL].points) == 3


def test_histories_skips_products_without_prices() -> None:
    """A column without any value is left out, the other product still works."""
    histories = parse_histories(_history_workbook(), "AT", [HEATING_OIL, LPG])
    assert list(histories) == [HEATING_OIL]


def test_history_of_product_without_prices() -> None:
    """Asking for one product that has no prices is an error."""
    with pytest.raises(ParseError):
        parse_history(_history_workbook(), "AT", LPG)


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
