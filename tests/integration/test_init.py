"""Tests for setup, sensors, caching and the websocket command."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ATTRIBUTION, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.heating_prices.const import (
    CONF_ANNUAL_CONSUMPTION,
    CONF_CURRENT_FUEL,
    CONF_FUELS,
    CONF_LAST_PURCHASES,
    CONF_OWN_GAS_PRICE,
    CONF_PURCHASE_AMOUNT,
    CONF_PURCHASE_DATE,
    CONF_PURCHASE_TOTAL,
    DOMAIN,
    FUEL_GAS,
    FUEL_LPG,
    FUEL_OIL,
    FUEL_PELLETS,
)
from custom_components.heating_prices.diagnostics import (
    async_get_config_entry_diagnostics,
)


def entity_id(hass: HomeAssistant, entry: MockConfigEntry, unique: str) -> str:
    """Look up an entity by its unique id suffix."""
    found = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_{unique}"
    )
    assert found is not None, unique
    return found


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the entry and let background tasks finish."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_sensors(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Every fuel gets price, heat price, change and rating sensors."""
    await setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    oil = hass.states.get(entity_id(hass, config_entry, "heating_oil_price"))
    assert oil is not None
    assert float(oil.state) == 175.01
    assert oil.attributes["unit_of_measurement"] == "€/100 L"
    assert oil.attributes["period"] == "2026-10-26"
    assert "European Commission" in oil.attributes[ATTR_ATTRIBUTION]
    # The background history load merged a year of weekly values.
    assert oil.attributes["previous_price"] == 171.0
    assert oil.attributes["rating"] == "high"

    heat = hass.states.get(entity_id(hass, config_entry, "heating_oil_heat_price"))
    assert heat is not None and float(heat.state) == 17.5

    change = hass.states.get(entity_id(hass, config_entry, "heating_oil_change"))
    assert change is not None and float(change.state) == 2.3

    rating = hass.states.get(entity_id(hass, config_entry, "heating_oil_rating"))
    assert rating is not None and rating.state == "high"
    assert rating.attributes["price"] == 175.01
    assert rating.attributes["period"] == "2026-10-26"

    gas = hass.states.get(entity_id(hass, config_entry, "natural_gas_price"))
    assert gas is not None
    assert gas.attributes["estimated"] is True
    assert gas.attributes["official_period"] == "2026-S1"

    cheapest = hass.states.get(entity_id(hass, config_entry, "cheapest_fuel"))
    assert cheapest is not None and cheapest.state == "pellets"

    mock_client.bulletin_history.assert_awaited_once_with("DE", [FUEL_OIL])


async def test_lpg_sensors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """LPG is shown as a motor fuel price and stays out of the comparison."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_FUELS: [FUEL_OIL, FUEL_PELLETS, FUEL_GAS, FUEL_LPG],
            CONF_CURRENT_FUEL: FUEL_OIL,
            CONF_ANNUAL_CONSUMPTION: 2500,
        },
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    lpg = hass.states.get(entity_id(hass, config_entry, "lpg_price"))
    assert lpg is not None
    assert float(lpg.state) == 113.02
    assert lpg.attributes["unit_of_measurement"] == "€/100 L"
    assert lpg.attributes["price_basis"] == "motor_fuel"
    # Both products were read from the same history download.
    assert lpg.attributes["previous_price"] == 102.75
    mock_client.bulletin_history.assert_awaited_once_with("DE", [FUEL_OIL, FUEL_LPG])

    rating = hass.states.get(entity_id(hass, config_entry, "lpg_rating"))
    assert rating is not None and rating.state == "high"

    registry = er.async_get(hass)
    for unique in ("lpg_heat_price", "lpg_annual_cost"):
        assert (
            registry.async_get_entity_id(
                "sensor", DOMAIN, f"{config_entry.entry_id}_{unique}"
            )
            is None
        ), unique

    cheapest = hass.states.get(entity_id(hass, config_entry, "cheapest_fuel"))
    assert cheapest is not None
    assert cheapest.state == "pellets"
    assert "lpg_heat_price" not in cheapest.attributes
    assert FUEL_LPG not in cheapest.attributes["options"]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/data"})
    response: dict[str, Any] = await client.receive_json()
    entry = response["result"]["entries"][0]
    assert entry["fuels"][FUEL_LPG]["heat_price"] is None
    assert entry["fuels"][FUEL_LPG]["extra"]["price_basis"] == "motor_fuel"
    assert entry["fuels"][FUEL_LPG]["entities"]["heat_price"] is None
    assert entry["cheapest"] == "pellets"
    assert FUEL_LPG not in entry["annual"]["costs"]


async def test_comparison_needs_two_heating_fuels(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Oil and LPG alone are nothing to compare."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_FUELS: [FUEL_OIL, FUEL_LPG]}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{config_entry.entry_id}_cheapest_fuel"
        )
        is None
    )
    assert hass.states.get(entity_id(hass, config_entry, "lpg_price")) is not None


async def test_adding_lpg_loads_its_history(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """A cached oil history does not stop LPG from getting its own."""
    await setup(hass, config_entry)
    mock_client.bulletin_history.assert_awaited_once_with("DE", [FUEL_OIL])
    assert await hass.config_entries.async_unload(config_entry.entry_id)

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_FUELS: [FUEL_OIL, FUEL_LPG]}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_client.bulletin_history.assert_awaited_with("DE", [FUEL_OIL, FUEL_LPG])

    lpg = hass.states.get(entity_id(hass, config_entry, "lpg_price"))
    assert lpg is not None and lpg.attributes["previous_price"] == 102.75

    # Now that both are covered, a reload does not download the file again.
    mock_client.bulletin_history.reset_mock()
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_client.bulletin_history.assert_not_awaited()


async def test_deselected_fuel_is_removed(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Sensors and the device of a fuel disappear when it is deselected."""
    await setup(hass, config_entry)
    gas_price = entity_id(hass, config_entry, "natural_gas_price")
    gas_device = (DOMAIN, f"{config_entry.entry_id}_{FUEL_GAS}")
    oil_device = (DOMAIN, f"{config_entry.entry_id}_{FUEL_OIL}")

    def device_identifiers() -> set[tuple[str, str]]:
        return {
            identifier
            for device in dr.async_entries_for_config_entry(
                dr.async_get(hass), config_entry.entry_id
            )
            for identifier in device.identifiers
        }

    assert gas_device in device_identifiers()

    # Changing the options reloads the entry.
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_FUELS: [FUEL_OIL, FUEL_PELLETS]}
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert er.async_get(hass).async_get(gas_price) is None
    assert gas_device not in device_identifiers()
    assert oil_device in device_identifiers()
    assert hass.states.get(entity_id(hass, config_entry, "pellets_price")) is not None


async def test_unload(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """The entry unloads cleanly."""
    await setup(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_without_data(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Without any data and no cache the setup is retried later."""
    for method in (
        mock_client.heating_oil_latest,
        mock_client.pellets,
        mock_client.natural_gas,
    ):
        method.side_effect = ClientError()
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_cached_prices_survive_outage(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """After a restart during an outage the last prices are shown as stale."""
    await setup(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)

    for method in (
        mock_client.heating_oil_latest,
        mock_client.pellets,
        mock_client.natural_gas,
    ):
        method.side_effect = ClientError()
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    oil = hass.states.get(entity_id(hass, config_entry, "heating_oil_price"))
    assert oil is not None
    assert float(oil.state) == 175.01
    assert oil.attributes["stale"] is True


async def test_single_fuel_failure(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """A fuel without data becomes unavailable, the others keep working."""
    mock_client.natural_gas.side_effect = ClientError()
    await setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    gas = hass.states.get(entity_id(hass, config_entry, "natural_gas_price"))
    assert gas is not None and gas.state == STATE_UNAVAILABLE
    oil = hass.states.get(entity_id(hass, config_entry, "heating_oil_price"))
    assert oil is not None and float(oil.state) == 175.01


async def test_own_price(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Own prices are compared with the market price."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_OWN_GAS_PRICE: 10.0}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    gas = hass.states.get(entity_id(hass, config_entry, "natural_gas_price"))
    assert gas is not None
    assert gas.attributes["own_price"] == 10.0
    assert gas.attributes["own_diff_pct"] < 0


async def test_websocket(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """The card receives prices, history and entity ids."""
    await setup(hass, config_entry)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/data"})
    response: dict[str, Any] = await client.receive_json()
    assert response["success"]

    entries = response["result"]["entries"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["country"] == "DE"
    assert entry["cheapest"] == "pellets"
    oil = entry["fuels"][FUEL_OIL]
    assert oil["price"] == 175.01
    assert len(oil["history"]) == 53
    assert oil["entities"]["price"] == entity_id(
        hass, config_entry, "heating_oil_price"
    )
    assert entry["fuels"][FUEL_GAS]["estimated"] is True

    await client.send_json_auto_id({"type": f"{DOMAIN}/data", "entry_id": "unknown"})
    response = await client.receive_json()
    assert response["result"]["entries"] == []


async def test_annual_costs(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """2,500 L of heating oil a year are compared with the other fuels."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_CURRENT_FUEL: FUEL_OIL, CONF_ANNUAL_CONSUMPTION: 2500},
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    # 25,000 kWh: oil 17.50 ct, pellets 9.18 ct (450 €/t), gas 11.42 ct per kWh.
    expected = {
        "heating_oil_annual_cost": 4375,
        "pellets_annual_cost": 2295,
        "natural_gas_annual_cost": 2855,
        "comparison_current_annual_cost": 4375,
        "comparison_potential_savings": 2080,
    }
    for unique, value in expected.items():
        state = hass.states.get(entity_id(hass, config_entry, unique))
        assert state is not None, unique
        assert float(state.state) == value, unique
    savings = hass.states.get(
        entity_id(hass, config_entry, "comparison_potential_savings")
    )
    assert savings is not None
    assert savings.attributes["cheapest_fuel"] == "pellets"
    assert savings.attributes["heat_demand_kwh"] == 25000

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/data"})
    response: dict[str, Any] = await client.receive_json()
    annual = response["result"]["entries"][0]["annual"]
    assert annual["consumption_unit"] == "L"
    assert annual["savings"] == 2080


async def test_no_cost_sensors_without_consumption(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Without a consumption the calculator stays off."""
    await setup(hass, config_entry)
    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id(
            "sensor", DOMAIN, f"{config_entry.entry_id}_heating_oil_annual_cost"
        )
        is None
    )


async def test_last_purchase(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """3,000 L bought for 3,600 € are compared with today's 175.01 €/100 L."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_LAST_PURCHASES: {
                FUEL_OIL: {
                    CONF_PURCHASE_DATE: "2026-03-16",
                    CONF_PURCHASE_AMOUNT: 3000,
                    CONF_PURCHASE_TOTAL: 3600,
                }
            }
        },
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    difference = hass.states.get(
        entity_id(hass, config_entry, "heating_oil_purchase_difference")
    )
    assert difference is not None
    assert float(difference.state) == 1650
    assert difference.attributes["unit_of_measurement"] == "EUR"
    assert difference.attributes["paid_price"] == 120.0
    assert difference.attributes["cost_now"] == 5250
    assert difference.attributes["market_price_then"] == 140.0

    change = hass.states.get(
        entity_id(hass, config_entry, "heating_oil_purchase_change")
    )
    assert change is not None and float(change.state) == 45.8

    # Only fuels with a purchase get these sensors.
    assert (
        er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{config_entry.entry_id}_pellets_purchase_difference"
        )
        is None
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/data"})
    response: dict[str, Any] = await client.receive_json()
    fuels = response["result"]["entries"][0]["fuels"]
    assert fuels[FUEL_OIL]["last_purchase"]["cost_now"] == 5250
    assert fuels[FUEL_OIL]["last_purchase"]["date"] == "2026-03-16"
    assert fuels[FUEL_PELLETS]["last_purchase"] is None

    # Removing the purchase removes its sensors.
    hass.config_entries.async_update_entry(config_entry, options={})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (
        er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{config_entry.entry_id}_heating_oil_purchase_difference"
        )
        is None
    )


async def test_last_purchase_of_lpg(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Heating gas follows the trend of the motor fuel price since the purchase."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_FUELS: [FUEL_OIL, FUEL_LPG],
            CONF_LAST_PURCHASES: {
                FUEL_LPG: {
                    CONF_PURCHASE_DATE: "2026-03-16",
                    CONF_PURCHASE_AMOUNT: 2000,
                    CONF_PURCHASE_TOTAL: 1300,
                }
            },
        },
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    # 95.00 €/100 L at the time of the purchase, 113.02 €/100 L today.
    difference = hass.states.get(
        entity_id(hass, config_entry, "lpg_purchase_difference")
    )
    assert difference is not None
    assert float(difference.state) == 247
    assert difference.attributes["estimated"] is True
    assert difference.attributes["paid_price"] == 65.0
    assert difference.attributes["cost_now"] == 1547


async def test_diagnostics(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Diagnostics summarise settings and prices."""
    await setup(hass, config_entry)
    result = await async_get_config_entry_diagnostics(hass, config_entry)
    assert result["settings"]["country"] == "DE"
    assert result["fuels"][FUEL_OIL]["history_points"] == 53
