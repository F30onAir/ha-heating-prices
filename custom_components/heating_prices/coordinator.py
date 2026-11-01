"""Coordinator that keeps the prices of one config entry up to date."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import SOURCE_ERRORS, PriceClient
from .const import (
    CONF_COUNTRY,
    CONF_FUELS,
    CONF_GAS_BAND,
    CONF_PELLET_QUANTITY,
    CONF_PELLET_REGION,
    DEFAULT_GAS_BAND,
    DEFAULT_PELLET_QUANTITY,
    DOMAIN,
    FUEL_GAS,
    FUEL_OIL,
    FUEL_PELLETS,
    OIL_HISTORY_MAX_AGE,
    PELLET_REGION_NATIONAL,
    UPDATE_INTERVAL,
)
from .models import FuelPrice
from .providers import PriceSeries

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1

type HeatingPricesConfigEntry = ConfigEntry[HeatingPricesCoordinator]


def _merge(
    older: list[tuple[date, float]], newer: list[tuple[date, float]]
) -> list[tuple[date, float]]:
    """Merge two series; values from the newer one win."""
    merged = dict(older)
    merged.update(newer)
    return sorted(merged.items())


class HeatingPricesCoordinator(DataUpdateCoordinator[dict[str, FuelPrice]]):
    """Fetch all enabled fuels and keep their history."""

    config_entry: HeatingPricesConfigEntry

    def __init__(self, hass: HomeAssistant, entry: HeatingPricesConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = PriceClient(hass)
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._cache: dict[str, Any] = {}
        self._history_task: asyncio.Task[None] | None = None
        self.last_fetched: datetime | None = None

    @property
    def settings(self) -> dict[str, Any]:
        """Entry data with options applied on top."""
        return {**self.config_entry.data, **self.config_entry.options}

    @property
    def country(self) -> str:
        """Configured country."""
        return self.settings[CONF_COUNTRY]

    @property
    def fuels(self) -> list[str]:
        """Enabled fuels."""
        return list(self.settings[CONF_FUELS])

    def _signature(self, fuel: str) -> str:
        """Identify the settings a cached series belongs to."""
        settings = self.settings
        if fuel == FUEL_PELLETS:
            return "/".join(
                (
                    settings.get(CONF_PELLET_REGION, PELLET_REGION_NATIONAL),
                    settings.get(CONF_PELLET_QUANTITY, DEFAULT_PELLET_QUANTITY),
                )
            )
        if fuel == FUEL_GAS:
            return f"{self.country}/{settings.get(CONF_GAS_BAND, DEFAULT_GAS_BAND)}"
        return self.country

    def _cached(self, fuel: str) -> FuelPrice | None:
        entry = self._cache.get("fuels", {}).get(fuel)
        if not entry or entry.get("signature") != self._signature(fuel):
            return None
        return FuelPrice.from_dict(entry["data"])

    def _remember(self, price: FuelPrice) -> None:
        self._cache.setdefault("fuels", {})[price.fuel] = {
            "signature": self._signature(price.fuel),
            "data": price.as_dict(),
        }

    async def _async_setup(self) -> None:
        """Load cached prices so sensors have values right after a restart."""
        self._cache = await self._store.async_load() or {}

    async def _fetch(self, fuel: str) -> FuelPrice:
        settings = self.settings
        if fuel == FUEL_OIL:
            series = await self.client.heating_oil_latest(self.country)
        elif fuel == FUEL_PELLETS:
            series = await self.client.pellets(
                settings.get(CONF_PELLET_REGION, PELLET_REGION_NATIONAL),
                settings.get(CONF_PELLET_QUANTITY, DEFAULT_PELLET_QUANTITY),
            )
        else:
            series = await self.client.natural_gas(
                self.country, settings.get(CONF_GAS_BAND, DEFAULT_GAS_BAND)
            )
        price = FuelPrice.from_series(fuel, series)

        cached = self._cached(fuel)
        if cached and fuel != FUEL_GAS:
            # Oil and pellet prices are final once published, so the history
            # can grow beyond what the source still lists. Gas values are
            # estimates that are recalculated, so they are always replaced.
            price.history = _merge(cached.history, price.history)
        return price

    async def _async_update_data(self) -> dict[str, FuelPrice]:
        fuels = self.fuels
        results = await asyncio.gather(
            *(self._fetch(fuel) for fuel in fuels), return_exceptions=True
        )

        data: dict[str, FuelPrice] = {}
        failed: list[str] = []
        for fuel, result in zip(fuels, results, strict=True):
            if isinstance(result, FuelPrice):
                data[fuel] = result
                self._remember(result)
                continue
            if not isinstance(result, SOURCE_ERRORS):
                raise result
            _LOGGER.warning("Could not update %s prices: %s", fuel, result)
            if (cached := self._cached(fuel)) is not None:
                cached.stale = True
                data[fuel] = cached
            else:
                failed.append(fuel)

        if not data:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"fuels": ", ".join(failed)},
            )

        self.last_fetched = dt_util.utcnow()
        await self._store.async_save(self._cache)
        if FUEL_OIL in data and self._oil_history_outdated():
            self._schedule_oil_history(data[FUEL_OIL])
        return data

    def _oil_history_outdated(self) -> bool:
        stored = self._cache.get("oil_history")
        if not stored or stored.get("country") != self.country:
            return True
        fetched = dt_util.parse_datetime(stored.get("fetched", ""))
        return fetched is None or dt_util.utcnow() - fetched > OIL_HISTORY_MAX_AGE

    def _schedule_oil_history(self, price: FuelPrice) -> None:
        """Load the long oil history in the background, it takes a while."""
        if self._history_task is not None and not self._history_task.done():
            return
        self._history_task = self.config_entry.async_create_background_task(
            self.hass, self._async_load_oil_history(price), f"{DOMAIN}_oil_history"
        )

    async def _async_load_oil_history(self, price: FuelPrice) -> None:
        try:
            series: PriceSeries = await self.client.heating_oil_history(self.country)
        except SOURCE_ERRORS as err:
            _LOGGER.warning("Could not load the heating oil price history: %s", err)
            return

        # The task may finish before the refresh that started it has stored its
        # result, so merge into the object that is (or will be) in self.data;
        # a later refresh may already have replaced it.
        if self.data and FUEL_OIL in self.data:
            price = self.data[FUEL_OIL]
        price.history = _merge(series.points, price.history)
        self._remember(price)
        # Remember when the full file was read so it is not downloaded again
        # too soon; the merged history itself is cached with the oil price.
        self._cache["oil_history"] = {
            "country": self.country,
            "fetched": dt_util.utcnow().isoformat(),
        }
        await self._store.async_save(self._cache)

        if self.data and self.data.get(FUEL_OIL) is price:
            self.async_set_updated_data(dict(self.data))

    async def async_remove_store(self) -> None:
        """Delete the cache when the entry is removed."""
        await self._store.async_remove()
