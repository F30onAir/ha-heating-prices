"""Price model shared by sensors, the websocket API and diagnostics."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import fmean
from typing import Any

from .const import (
    FUEL_GAS,
    FUEL_OIL,
    FUEL_PELLETS,
    FUEL_UNITS,
    OIL_KWH_PER_LITRE,
    PELLETS_KWH_PER_KG,
    RATING_HIGH,
    RATING_LOW,
    RATING_NORMAL,
)
from .providers import PriceSeries

_YEAR = timedelta(days=365)
# Ratings need enough history to be meaningful.
_MIN_RATING_POINTS = 6
_LOW_PERCENTILE = 0.25
_HIGH_PERCENTILE = 0.75


def heat_price(fuel: str, price: float) -> float:
    """Convert a fuel price to ct per kWh of heat."""
    if fuel == FUEL_OIL:
        # €/100 L -> €/L -> €/kWh -> ct/kWh
        return round(price / OIL_KWH_PER_LITRE, 2)
    if fuel == FUEL_PELLETS:
        # €/t -> €/kg -> €/kWh -> ct/kWh
        return round(price / 10 / PELLETS_KWH_PER_KG, 2)
    if fuel == FUEL_GAS:
        return round(price, 2)
    raise ValueError(f"Unknown fuel {fuel}")


@dataclass(slots=True)
class FuelPrice:
    """Current price of one fuel with its history."""

    fuel: str
    history: list[tuple[date, float]]
    source: str
    source_url: str
    attribution: str
    estimated: bool = False
    stale: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_series(cls, fuel: str, series: PriceSeries) -> FuelPrice:
        """Build from a parsed source series."""
        return cls(
            fuel=fuel,
            history=list(series.points),
            source=series.source,
            source_url=series.source_url,
            attribution=series.attribution,
            estimated=series.estimated,
            extra=dict(series.extra),
        )

    @property
    def unit(self) -> str:
        """Unit of the price."""
        return FUEL_UNITS[self.fuel]

    @property
    def period(self) -> date:
        """Date the current price refers to."""
        return self.history[-1][0]

    @property
    def price(self) -> float:
        """Current price."""
        return self.history[-1][1]

    @property
    def previous_price(self) -> float | None:
        """Price of the previous period."""
        return self.history[-2][1] if len(self.history) > 1 else None

    @property
    def change_pct(self) -> float | None:
        """Change against the previous period in percent."""
        previous = self.previous_price
        if not previous:
            return None
        return round((self.price - previous) / previous * 100, 1)

    @property
    def heat_price(self) -> float:
        """Current price in ct per kWh of heat."""
        return heat_price(self.fuel, self.price)

    def last_year(self) -> list[float]:
        """Prices of the twelve months up to the current period."""
        dates = [point[0] for point in self.history]
        start = bisect_left(dates, self.period - _YEAR)
        return [value for _, value in self.history[start:]]

    @property
    def min_12m(self) -> float | None:
        """Lowest price within twelve months."""
        values = self.last_year()
        return min(values) if values else None

    @property
    def max_12m(self) -> float | None:
        """Highest price within twelve months."""
        values = self.last_year()
        return max(values) if values else None

    @property
    def avg_12m(self) -> float | None:
        """Average price within twelve months."""
        values = self.last_year()
        return round(fmean(values), 2) if values else None

    @property
    def rating(self) -> str | None:
        """Rate the current price against the last twelve months."""
        values = self.last_year()
        if len(values) < _MIN_RATING_POINTS:
            return None
        below = sum(1 for value in values if value < self.price)
        percentile = below / (len(values) - 1)
        if percentile <= _LOW_PERCENTILE:
            return RATING_LOW
        if percentile >= _HIGH_PERCENTILE:
            return RATING_HIGH
        return RATING_NORMAL

    def as_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "fuel": self.fuel,
            "history": [[when.isoformat(), value] for when, value in self.history],
            "source": self.source,
            "source_url": self.source_url,
            "attribution": self.attribution,
            "estimated": self.estimated,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FuelPrice:
        """Restore from storage."""
        return cls(
            fuel=data["fuel"],
            history=[
                (date.fromisoformat(when), float(value))
                for when, value in data["history"]
            ],
            source=data["source"],
            source_url=data["source_url"],
            attribution=data["attribution"],
            estimated=data.get("estimated", False),
            extra=data.get("extra", {}),
        )
