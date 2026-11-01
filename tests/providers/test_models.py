"""Tests for the price model."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from heating_prices.models import FuelPrice, annual_costs, heat_demand_kwh, heat_price


def weekly(
    values: list[float], end: date = date(2026, 10, 26)
) -> list[tuple[date, float]]:
    """Weekly points ending on the given date."""
    start = end - timedelta(weeks=len(values) - 1)
    return [(start + timedelta(weeks=i), value) for i, value in enumerate(values)]


def oil(values: list[float]) -> FuelPrice:
    """A heating oil price with the given weekly history."""
    return FuelPrice(
        fuel="heating_oil",
        history=weekly(values),
        source="EU Weekly Oil Bulletin",
        source_url="https://example.invalid",
        attribution="Source: test",
    )


@pytest.mark.parametrize(
    ("fuel", "price", "expected"),
    [
        ("heating_oil", 175.0, 17.5),
        ("pellets", 490.0, 10.0),
        ("natural_gas", 11.42, 11.42),
    ],
)
def test_heat_price(fuel: str, price: float, expected: float) -> None:
    """Prices are converted to ct per kWh of heat."""
    assert heat_price(fuel, price) == expected


def test_change_and_statistics() -> None:
    """Change and twelve-month statistics use the history."""
    price = oil([100.0, 120.0, 110.0, 130.0, 150.0, 140.0])
    assert price.price == 140.0
    assert price.previous_price == 150.0
    assert price.change_pct == -6.7
    assert (price.min_12m, price.max_12m, price.avg_12m) == (100.0, 150.0, 125.0)


def test_statistics_ignore_older_points() -> None:
    """Only the last twelve months count."""
    price = oil([10.0] + [100.0] * 60)
    assert price.min_12m == 100.0


@pytest.mark.parametrize(
    ("values", "rating"),
    [
        ([150, 140, 130, 120, 110, 100], "low"),
        ([100, 110, 120, 130, 140, 150], "high"),
        ([100, 150, 110, 140, 120, 125, 130], "normal"),
        ([100, 120], None),
    ],
)
def test_rating(values: list[float], rating: str | None) -> None:
    """The current price is rated against the last twelve months."""
    assert oil([float(v) for v in values]).rating == rating


def test_single_point() -> None:
    """A single point has no change."""
    price = oil([100.0])
    assert price.previous_price is None
    assert price.change_pct is None


def _price(fuel: str, value: float) -> FuelPrice:
    return FuelPrice(
        fuel=fuel,
        history=[(date(2026, 10, 1), value)],
        source="test",
        source_url="https://example.invalid",
        attribution="test",
    )


PRICES = {
    "heating_oil": _price("heating_oil", 175.0),  # 17.5 ct/kWh
    "pellets": _price("pellets", 490.0),  # 10.0 ct/kWh
    "natural_gas": _price("natural_gas", 11.5),  # 11.5 ct/kWh
}


@pytest.mark.parametrize(
    ("fuel", "consumption", "kwh"),
    [
        ("heating_oil", 2500, 25000),
        ("pellets", 5, 24500),
        ("natural_gas", 20000, 20000),
    ],
)
def test_heat_demand(fuel: str, consumption: float, kwh: float) -> None:
    """Consumption in L, t or kWh is converted to kWh of heat."""
    assert heat_demand_kwh(fuel, consumption) == pytest.approx(kwh)


def test_annual_costs_at_market_prices() -> None:
    """2,500 L of oil equal 25,000 kWh; pellets are cheapest."""
    costs = annual_costs("heating_oil", 2500, PRICES)
    assert costs is not None
    assert costs.costs == {"heating_oil": 4375, "pellets": 2500, "natural_gas": 2875}
    assert costs.current_cost == 4375
    assert costs.cheapest == "pellets"
    assert costs.savings == 1875


def test_annual_costs_with_own_price() -> None:
    """The user's own price is used for the fuel they heat with."""
    costs = annual_costs("natural_gas", 20000, PRICES, own_price=9.0)
    assert costs is not None
    assert costs.current_cost == 1800
    # Pellets at 10 ct/kWh cost 2,000 €, so the own gas tariff is cheapest.
    assert costs.savings == 0


def test_annual_costs_without_consumption() -> None:
    """Zero consumption disables the calculator."""
    assert annual_costs("pellets", 0, PRICES) is None


def test_annual_costs_current_fuel_missing() -> None:
    """Without a price for the current fuel there is nothing to save against."""
    costs = annual_costs("heating_oil", 2500, {"pellets": PRICES["pellets"]})
    assert costs is not None
    assert costs.current_cost is None
    assert costs.savings is None


def test_round_trip() -> None:
    """Prices survive storage."""
    price = oil([100.0, 101.5])
    price.extra = {"region": "south"}
    restored = FuelPrice.from_dict(price.as_dict())
    assert restored == price
