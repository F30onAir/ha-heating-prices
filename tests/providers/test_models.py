"""Tests for the price model."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from heating_prices.models import (
    FuelPrice,
    annual_costs,
    heat_demand_kwh,
    heat_price,
    purchase_comparison,
)


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


def test_lpg_has_no_heat_price() -> None:
    """The LPG price is for motor fuel, so it is not converted to heat."""
    assert _price("lpg", 113.0).heat_price is None
    assert _price("lpg", 113.0).unit == "€/100 L"


def test_annual_costs_leave_out_lpg() -> None:
    """A cheap motor fuel price must not show up as a heating saving."""
    prices = {**PRICES, "lpg": _price("lpg", 1.0)}
    costs = annual_costs("heating_oil", 2500, prices)
    assert costs is not None
    assert "lpg" not in costs.costs
    assert costs.cheapest == "pellets"


def test_price_on() -> None:
    """A day gets the last price published up to then."""
    price = oil([100.0, 110.0, 120.0])  # 12, 19 and 26 October
    assert price.price_on(date(2026, 10, 12)) == 100.0
    assert price.price_on(date(2026, 10, 18)) == 100.0
    assert price.price_on(date(2026, 11, 1)) == 120.0
    assert price.price_on(date(2026, 10, 11)) is None


def _purchase(day: str, amount: float, total: float) -> dict[str, str | float]:
    return {"date": day, "amount": amount, "total_price": total}


def test_purchase_against_todays_price() -> None:
    """3,000 L for 3,600 € cost 5,250 € at today's 175.01 €/100 L."""
    comparison = purchase_comparison(
        oil([140.0, 175.01]), _purchase("2026-10-20", 3000, 3600)
    )
    assert comparison is not None
    assert comparison.paid_price == 120.0
    assert comparison.market_price_then == 140.0
    assert comparison.amount_unit == "L"
    assert comparison.cost_now == 5250
    assert comparison.difference == 1650
    assert comparison.change_pct == 45.8
    assert comparison.estimated is False


def test_purchase_more_expensive_than_today() -> None:
    """A price that fell since the purchase gives a negative difference."""
    comparison = purchase_comparison(
        oil([175.0]), _purchase("2026-10-26", 3000, 6000)
    )
    assert comparison is not None
    assert comparison.paid_price == 200.0
    assert comparison.difference == -750
    assert comparison.change_pct == -12.5


@pytest.mark.parametrize(
    ("fuel", "value", "amount", "total", "paid", "cost_now", "unit"),
    [
        ("pellets", 450.0, 6, 2400, 400.0, 2700, "t"),
        ("natural_gas", 11.5, 20000, 2000, 10.0, 2300, "kWh"),
    ],
)
def test_purchase_units(
    fuel: str,
    value: float,
    amount: float,
    total: float,
    paid: float,
    cost_now: int,
    unit: str,
) -> None:
    """Paid prices use the fuel's price unit: €/t for pellets, ct/kWh for gas."""
    comparison = purchase_comparison(
        _price(fuel, value), _purchase("2026-10-01", amount, total)
    )
    assert comparison is not None
    assert comparison.paid_price == paid
    assert comparison.cost_now == cost_now
    assert comparison.amount_unit == unit


def test_purchase_of_lpg_follows_the_market() -> None:
    """Heating gas is not compared with the motor fuel price directly."""
    price = oil([95.0, 113.02])
    price.fuel = "lpg"
    comparison = purchase_comparison(price, _purchase("2026-10-19", 2000, 1300))
    assert comparison is not None
    assert comparison.paid_price == 65.0
    assert comparison.market_price_then == 95.0
    assert comparison.cost_now == 1547
    assert comparison.difference == 247
    assert comparison.change_pct == 19.0
    assert comparison.estimated is True


def test_purchase_of_lpg_before_the_history() -> None:
    """Without the price at the time of purchase there is no trend to apply."""
    price = _price("lpg", 113.0)
    assert purchase_comparison(price, _purchase("2026-09-30", 2000, 1300)) is None


def test_round_trip() -> None:
    """Prices survive storage."""
    price = oil([100.0, 101.5])
    price.extra = {"region": "south"}
    restored = FuelPrice.from_dict(price.as_dict())
    assert restored == price
