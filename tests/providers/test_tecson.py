"""Tests for the TECSON daily price parser.

The page below is written by hand with invented prices. TECSON's permission does
not cover keeping a copy of its page in this repository.
"""

from __future__ import annotations

from datetime import date

import pytest

from heating_prices.providers import ParseError
from heating_prices.providers.tecson import DailyPrice, parse


def page(
    day: str = "Dienstag 3. Feb.",
    price: str = "123,4",
    footnote: str = "* Preis&shy;bezug:&nbsp; Liefer&shy;menge 3000 L, inkl. MwSt.",
) -> str:
    """A price table in the structure of the TECSON page."""
    return f"""
    <h3>Preis&shy;ver&shy;&auml;n&shy;de&shy;rung beim Heiz&ouml;l</h3>
    <table><tbody>
    <tr>
    <td><span><strong>Referenzpreis aktuell *)</strong></span><br>(DE-Mittelpreis)</td>
    <td><strong><span>{day}</span><br><span>&Oslash; {price}&nbsp;ct/l</span></strong></td>
    </tr>
    <tr><td>1,0% g&uuml;nstiger als gestern</td><td>mit&nbsp;124,6&nbsp;ct/l</td></tr>
    </tbody></table>
    <p><span>{footnote}</span></p>
    """


def test_parse() -> None:
    """The price of the day is read with its date and delivery quantity."""
    assert parse(page(), date(2026, 2, 3)) == DailyPrice(
        day=date(2026, 2, 3), price=123.4, quantity=3000
    )


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        ("Montag 2. März", date(2026, 3, 2)),
        ("Montag 2. Mrz.", date(2026, 3, 2)),
        ("Freitag 1. Mai", date(2026, 5, 1)),
        ("Montag 1. Juni", date(2026, 6, 1)),
        ("Dienstag 1. Sept.", date(2026, 9, 1)),
        ("Samstag 31. Okt.", date(2026, 10, 31)),
    ],
)
def test_month_names(day: str, expected: date) -> None:
    """Months may be written out or abbreviated."""
    assert parse(page(day=day), date(2026, 12, 1)).day == expected


def test_year_change() -> None:
    """On New Year's Day the page can still show December of the last year."""
    assert parse(page(day="Donnerstag 31. Dez."), date(2027, 1, 1)).day == date(
        2026, 12, 31
    )


def test_quantity_comes_from_the_page() -> None:
    """A changed reference quantity is passed on instead of being assumed."""
    footnote = "* Preisbezug: Liefermenge 2.500 L, inkl. MwSt."
    assert parse(page(footnote=footnote), date(2026, 2, 3)).quantity == 2500


def test_round_trip() -> None:
    """Daily prices survive storage."""
    price = parse(page(), date(2026, 2, 3))
    assert DailyPrice.from_dict(price.as_dict()) == price


@pytest.mark.parametrize(
    "content",
    [
        "<html><body><p>Neue Seite</p></body></html>",
        page(price="neu"),
        page(price="9,9"),
        page(price="1234,5"),
        page(day="Montag 2. Foo."),
        page(footnote=""),
    ],
)
def test_page_without_a_usable_price(content: str) -> None:
    """A redesigned page raises a parse error instead of showing a wrong value."""
    with pytest.raises(ParseError):
        parse(content, date(2026, 2, 3))
