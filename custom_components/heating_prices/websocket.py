"""Websocket command that feeds the dashboard card."""

from __future__ import annotations

from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
import voluptuous as vol

from .const import CONF_COUNTRY, CONSUMPTION_UNITS, DOMAIN
from .coordinator import HeatingPricesConfigEntry
from .models import FuelPrice

SENSOR_KEYS = ("price", "heat_price", "change", "rating")


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    """Register the websocket command."""
    websocket_api.async_register_command(hass, ws_data)


def fuel_payload(price: FuelPrice, own_price: float | None) -> dict[str, Any]:
    """Everything the card shows for one fuel."""
    payload: dict[str, Any] = {
        "price": price.price,
        "unit": price.unit,
        "period": price.period.isoformat(),
        "previous_price": price.previous_price,
        "change_pct": price.change_pct,
        "heat_price": price.heat_price,
        "min_12m": price.min_12m,
        "max_12m": price.max_12m,
        "avg_12m": price.avg_12m,
        "rating": price.rating,
        "estimated": price.estimated,
        "stale": price.stale,
        "source": price.source,
        "source_url": price.source_url,
        "attribution": price.attribution,
        "extra": price.extra,
        "history": [[when.isoformat(), value] for when, value in price.history],
        "own_price": own_price,
        "own_diff_pct": None,
    }
    if own_price:
        payload["own_diff_pct"] = round(
            (own_price - price.price) / price.price * 100, 1
        )
    return payload


def cheapest_fuel(data: dict[str, FuelPrice]) -> str | None:
    """Fuel with the lowest price per kWh of heat."""
    prices = [price for price in data.values() if price.heat_price is not None]
    if len(prices) < 2:
        return None
    return min(prices, key=lambda price: price.heat_price).fuel


def _entry_payload(
    hass: HomeAssistant, entry: HeatingPricesConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    registry = er.async_get(hass)
    settings = coordinator.settings
    fuels: dict[str, Any] = {}
    for fuel, price in (coordinator.data or {}).items():
        payload = fuel_payload(price, coordinator.own_price(fuel))
        payload["entities"] = {
            key: registry.async_get_entity_id(
                "sensor", DOMAIN, f"{entry.entry_id}_{fuel}_{key}"
            )
            for key in SENSOR_KEYS
        }
        purchase = coordinator.last_purchase(fuel)
        payload["last_purchase"] = purchase.as_dict() if purchase else None
        fuels[fuel] = payload
    costs = coordinator.annual_costs
    annual = None
    if costs is not None:
        annual = costs.as_dict()
        annual["consumption_unit"] = CONSUMPTION_UNITS[costs.current_fuel]
    return {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "country": settings[CONF_COUNTRY],
        "fuels": fuels,
        "cheapest": cheapest_fuel(coordinator.data or {}),
        "annual": annual,
        "last_update": (
            coordinator.last_fetched.isoformat() if coordinator.last_fetched else None
        ),
    }


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/data",
        vol.Optional("entry_id"): str,
    }
)
@callback
def ws_data(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return prices and history of all (or one) loaded entries."""
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
        and msg.get("entry_id") in (None, entry.entry_id)
    ]
    connection.send_result(
        msg["id"], {"entries": [_entry_payload(hass, entry) for entry in entries]}
    )
