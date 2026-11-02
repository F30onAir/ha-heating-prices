"""Price model shared by sensors, the websocket API and diagnostics."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import fmean
from typing import Any

from .const import (
    COMPARABLE_FUELS,
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


def heat_demand_kwh(fuel: str, consumption: float) -> float:
    """Heat content of an annual consumption in L (oil), t (pellets) or kWh (gas)."""
    if fuel == FUEL_OIL:
        return consumption * OIL_KWH_PER_LITRE
    if fuel == FUEL_PELLETS:
        return consumption * 1000 * PELLETS_KWH_PER_KG
    if fuel == FUEL_GAS:
        return consumption
    raise ValueError(f"Unknown fuel {fuel}")


@dataclass(slots=True)
class AnnualCosts:
    """What a year of heating costs with each fuel for the user's heat demand.

    Boiler efficiencies are not taken into account, so the comparison shows
    fuel costs for the same amount of heat content.
    """

    current_fuel: str
    consumption: float
    heat_kwh: float
    # € per year at market prices, per enabled fuel.
    costs: dict[str, int]
    # € per year for the current fuel, at the user's own price if one is set.
    current_cost: int | None
    cheapest: str | None
    # € per year saved by switching to the cheapest fuel.
    savings: int | None

    def as_dict(self) -> dict[str, Any]:
        """Serialize for the websocket API and diagnostics."""
        return {
            "current_fuel": self.current_fuel,
            "consumption": self.consumption,
            "heat_kwh": round(self.heat_kwh),
            "costs": self.costs,
            "current_cost": self.current_cost,
            "cheapest": self.cheapest,
            "savings": self.savings,
        }


def annual_costs(
    current_fuel: str,
    consumption: float,
    prices: dict[str, FuelPrice],
    own_price: float | None = None,
) -> AnnualCosts | None:
    """Compare yearly costs of all fuels for the user's heat demand."""
    if consumption <= 0:
        return None
    heat_kwh = heat_demand_kwh(current_fuel, consumption)
    costs = {
        fuel: round(heat_kwh * price.heat_price / 100)
        for fuel, price in prices.items()
        if price.heat_price is not None
    }
    if own_price:
        current_cost: int | None = round(
            heat_kwh * heat_price(current_fuel, own_price) / 100
        )
    else:
        current_cost = costs.get(current_fuel)
    cheapest = min(costs, key=costs.__getitem__) if costs else None
    savings = (
        max(0, current_cost - costs[cheapest])
        if current_cost is not None and cheapest is not None
        else None
    )
    return AnnualCosts(
        current_fuel=current_fuel,
        consumption=consumption,
        heat_kwh=heat_kwh,
        costs=costs,
        current_cost=current_cost,
        cheapest=cheapest,
        savings=savings,
    )


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
    def heat_price(self) -> float | None:
        """Current price in ct per kWh of heat, if it can be compared."""
        if self.fuel not in COMPARABLE_FUELS:
            return None
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
