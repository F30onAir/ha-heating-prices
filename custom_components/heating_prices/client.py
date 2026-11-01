"""Download and parse price data from the public sources."""

from __future__ import annotations

import json
from typing import Any

from aiohttp import ClientError, ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import USER_AGENT
from .providers import ParseError, PriceSeries, depi, eurostat, oil_bulletin

# Errors that mean "the source could not be read right now".
SOURCE_ERRORS = (ClientError, TimeoutError, ParseError, ValueError)

_TIMEOUT = ClientTimeout(total=30)
_HISTORY_TIMEOUT = ClientTimeout(total=180)


class PriceClient:
    """Fetch prices for one Home Assistant instance."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the client."""
        self._hass = hass
        self._session = async_get_clientsession(hass)

    async def _get(self, url: str, timeout: ClientTimeout = _TIMEOUT) -> bytes:
        async with self._session.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=timeout
        ) as response:
            response.raise_for_status()
            return await response.read()

    async def _get_json(self, url: str) -> dict[str, Any]:
        return json.loads(await self._get(url))

    async def heating_oil_latest(self, country: str) -> PriceSeries:
        """Return this week's heating oil price."""
        content = await self._get(oil_bulletin.LATEST_URL)
        return await self._hass.async_add_executor_job(
            oil_bulletin.parse_latest, content, country
        )

    async def heating_oil_history(self, country: str) -> PriceSeries:
        """Return all weekly heating oil prices since 2005 (large download)."""
        content = await self._get(oil_bulletin.HISTORY_URL, _HISTORY_TIMEOUT)
        return await self._hass.async_add_executor_job(
            oil_bulletin.parse_history, content, country
        )

    async def pellets(self, region: str, quantity: str) -> PriceSeries:
        """Return the monthly DEPI pellet prices."""
        html = (await self._get(depi.URL)).decode("utf-8", errors="replace")
        prices = await self._hass.async_add_executor_job(depi.parse, html)
        return depi.select(prices, region, quantity)

    async def natural_gas(self, country: str, band: str) -> PriceSeries:
        """Return household gas prices, carried forward to the latest month."""
        prices = await self._get_json(eurostat.gas_price_url(country, band))
        try:
            index: dict[str, Any] | None = await self._get_json(
                eurostat.gas_index_url(country)
            )
        except SOURCE_ERRORS:
            # Without the index we still have the official half-year price.
            index = None
        return eurostat.build_gas_series(prices, index)
