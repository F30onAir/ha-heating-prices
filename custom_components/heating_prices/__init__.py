"""Heating Prices: heating oil, pellet, natural gas and LPG prices from open data."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .card import async_register_card
from .const import DOMAIN
from .coordinator import HeatingPricesConfigEntry, HeatingPricesCoordinator
from .websocket import async_register_websocket

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the dashboard card and its websocket command."""
    async_register_websocket(hass)
    await async_register_card(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: HeatingPricesConfigEntry
) -> bool:
    """Set up Heating Prices from a config entry."""
    coordinator = HeatingPricesCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HeatingPricesConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: HeatingPricesConfigEntry
) -> None:
    """Delete cached prices of a removed entry."""
    await HeatingPricesCoordinator(hass, entry).async_remove_store()


async def _async_reload(hass: HomeAssistant, entry: HeatingPricesConfigEntry) -> None:
    """Apply changed options."""
    await hass.config_entries.async_reload(entry.entry_id)
