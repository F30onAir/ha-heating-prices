"""Tests for the config and options flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from aiohttp import ClientError
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.heating_prices.const import (
    CONF_COUNTRY,
    CONF_FUELS,
    CONF_GAS_BAND,
    CONF_OWN_GAS_PRICE,
    CONF_PELLET_QUANTITY,
    CONF_PELLET_REGION,
    DOMAIN,
    FUEL_GAS,
    FUEL_OIL,
    FUEL_PELLETS,
)
from custom_components.heating_prices.providers import ParseError


async def test_full_flow(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """All fuels walk through the pellet and gas steps."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COUNTRY: "DE", CONF_FUELS: [FUEL_OIL, FUEL_PELLETS, FUEL_GAS]},
    )
    assert result["step_id"] == "pellets"
    mock_client.heating_oil_latest.assert_awaited_with("DE")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PELLET_REGION: "south", CONF_PELLET_QUANTITY: "3"}
    )
    assert result["step_id"] == "gas"
    mock_client.pellets.assert_awaited_with("south", "3")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_GAS_BAND: "d2"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Germany"
    assert result["data"] == {
        CONF_COUNTRY: "DE",
        CONF_FUELS: [FUEL_OIL, FUEL_PELLETS, FUEL_GAS],
        CONF_PELLET_REGION: "south",
        CONF_PELLET_QUANTITY: "3",
        CONF_GAS_BAND: "d2",
    }
    assert result["result"].unique_id == "DE"


async def test_gas_only_skips_pellets(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Without pellets the pellet step is skipped and oil is not checked."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COUNTRY: "AT", CONF_FUELS: [FUEL_GAS]}
    )
    assert result["step_id"] == "gas"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_GAS_BAND: "d3"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_client.heating_oil_latest.assert_not_awaited()
    mock_client.natural_gas.assert_awaited_with("AT", "d3")


async def test_pellets_outside_germany(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Pellet prices exist for Germany only."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COUNTRY: "AT", CONF_FUELS: [FUEL_PELLETS]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_FUELS: "pellets_unavailable"}


@pytest.mark.parametrize(
    ("error", "expected"),
    [(ParseError("no column"), "oil_no_data"), (ClientError(), "oil_cannot_connect")],
)
async def test_oil_errors_recover(
    hass: HomeAssistant, mock_client: AsyncMock, error: Exception, expected: str
) -> None:
    """Source problems are shown and the user can try again."""
    mock_client.heating_oil_latest.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COUNTRY: "DE", CONF_FUELS: [FUEL_OIL]}
    )
    assert result["errors"] == {"base": expected}

    mock_client.heating_oil_latest.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COUNTRY: "DE", CONF_FUELS: [FUEL_OIL]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_national_three_tonnes(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """3 t is only published per region."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COUNTRY: "DE", CONF_FUELS: [FUEL_PELLETS]}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PELLET_REGION: "national", CONF_PELLET_QUANTITY: "3"}
    )
    assert result["errors"] == {CONF_PELLET_QUANTITY: "quantity_regional_only"}
    mock_client.pellets.assert_not_awaited()


async def test_already_configured(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Each country can be set up once."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COUNTRY: "DE", CONF_FUELS: [FUEL_OIL]}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Own prices and settings can be changed later."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_OWN_GAS_PRICE: 10.5,
            CONF_PELLET_REGION: "national",
            CONF_PELLET_QUANTITY: "3",
            CONF_GAS_BAND: "d2",
        },
    )
    assert result["errors"] == {CONF_PELLET_QUANTITY: "quantity_regional_only"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_OWN_GAS_PRICE: 10.5,
            CONF_PELLET_REGION: "south",
            CONF_PELLET_QUANTITY: "3",
            CONF_GAS_BAND: "d2",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert config_entry.options[CONF_OWN_GAS_PRICE] == 10.5
    mock_client.pellets.assert_awaited_with("south", "3")
