"""Diagnostics support for Heating Prices."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import HeatingPricesConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HeatingPricesConfigEntry
) -> dict[str, Any]:
    """Return settings and a summary of the current prices."""
    coordinator = entry.runtime_data
    return {
        "settings": coordinator.settings,
        "last_fetched": (
            coordinator.last_fetched.isoformat() if coordinator.last_fetched else None
        ),
        "fuels": {
            fuel: {
                "price": price.price,
                "unit": price.unit,
                "period": price.period.isoformat(),
                "history_points": len(price.history),
                "history_start": price.history[0][0].isoformat(),
                "estimated": price.estimated,
                "stale": price.stale,
                "source": price.source,
                "extra": price.extra,
            }
            for fuel, price in (coordinator.data or {}).items()
        },
    }
