"""Serve the bundled dashboard card."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)

CARD_FILE = Path(__file__).parent / "frontend" / "heating-prices-card.js"
CARD_URL = f"/{DOMAIN}/heating-prices-card.js"


async def async_register_card(hass: HomeAssistant) -> None:
    """Make the card available on every dashboard without manual resources."""
    if "frontend" not in hass.config.components or getattr(hass, "http", None) is None:
        _LOGGER.debug("Frontend not loaded, the card is not registered")
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=False)]
    )
    # The version query makes browsers load a new file after an update.
    add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")
