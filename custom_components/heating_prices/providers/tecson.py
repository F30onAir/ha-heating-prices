"""Daily heating oil price for Germany from TECSON.

TECSON publishes the average price of the day per 100 L for a delivery of 3,000 L,
VAT included. It allowed this integration to show that value with the source and a
link to the page below. TECSON has no API, so the value is read from the page. The
permission covers nothing else on the page, see NOTICE.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import html
import re
from typing import Any

from . import ParseError, parse_decimal

URL = "https://www.tecson.de/de/heizoelpreise.html"
SOURCE = "TECSON"
ATTRIBUTION = "Quelle: TECSON"

MONTHS = {
    "jan": 1, "feb": 2, "mär": 3, "mrz": 3, "apr": 4, "mai": 5, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12,
}  # fmt: skip

_HEADING = "Referenzpreis aktuell"
_TAG = re.compile(r"<[^>]+>")
_PRICE = re.compile(r"(\d{1,2})\.\s*([^\W\d_]+)\.?\s*Ø\s*(\d+(?:,\d+)?)\s*ct/l")
_QUANTITY = re.compile(r"Preisbezug:\s*Liefermenge\s*(\d[\d.]*)\s*L\b")
# Anything outside this range in ct/l means the page was misread.
_MIN_PRICE = 30
_MAX_PRICE = 500


@dataclass(slots=True)
class DailyPrice:
    """TECSON's average price of one day."""

    day: date
    # € per 100 L, which is the same number as ct per litre.
    price: float
    # Delivery in litres the price refers to.
    quantity: int

    def as_dict(self) -> dict[str, Any]:
        """Serialize for storage and the websocket API."""
        return {
            "date": self.day.isoformat(),
            "price": self.price,
            "quantity": self.quantity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DailyPrice:
        """Restore from storage."""
        return cls(
            day=date.fromisoformat(data["date"]),
            price=float(data["price"]),
            quantity=int(data["quantity"]),
        )


def _day(day: int, month_name: str, today: date) -> date:
    month = MONTHS.get(month_name[:3].lower())
    if month is None:
        raise ParseError(f"Unknown month {month_name}")
    result = date(today.year, month, day)
    # The page names no year, and on 1 January it can still show 31 December.
    if result > today + timedelta(days=1):
        return result.replace(year=today.year - 1)
    return result


def parse(page: str, today: date) -> DailyPrice:
    """Read the price of the day from the TECSON page."""
    text = html.unescape(page).replace("­", "")
    start = text.find(_HEADING)
    if start < 0:
        raise ParseError("No reference price table found")
    section = _TAG.sub(" ", text[start:])

    match = _PRICE.search(section)
    if match is None:
        raise ParseError("No reference price found")
    price = parse_decimal(match.group(3))
    if price is None or not _MIN_PRICE <= price <= _MAX_PRICE:
        raise ParseError(f"Implausible reference price {match.group(3)}")

    quantity = _QUANTITY.search(section)
    if quantity is None:
        raise ParseError("No delivery quantity found")

    return DailyPrice(
        day=_day(int(match.group(1)), match.group(2), today),
        price=price,
        quantity=int(quantity.group(1).replace(".", "")),
    )
