"""Fixtures for the Home Assistant tests."""

from __future__ import annotations

from collections.abc import Generator
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.heating_prices.const import (
    CONF_COUNTRY,
    CONF_FUELS,
    CONF_GAS_BAND,
    CONF_PELLET_QUANTITY,
    CONF_PELLET_REGION,
    DOMAIN,
    FUEL_GAS,
    FUEL_OIL,
    FUEL_PELLETS,
)
from custom_components.heating_prices.providers import PriceSeries


def _weekly(values: list[float], end: date) -> list[tuple[date, float]]:
    start = end - timedelta(weeks=len(values) - 1)
    return [(start + timedelta(weeks=i), value) for i, value in enumerate(values)]


def oil_latest() -> PriceSeries:
    """This week's heating oil price."""
    return PriceSeries(
        points=[(date(2026, 10, 26), 175.01)],
        source="EU Weekly Oil Bulletin",
        source_url="https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en",
        attribution="Source: European Commission, Weekly Oil Bulletin",
    )


def oil_history() -> PriceSeries:
    """A year of weekly heating oil prices before this week."""
    return PriceSeries(
        points=_weekly([120.0 + i for i in range(52)], date(2026, 10, 19)),
        source="EU Weekly Oil Bulletin",
        source_url="https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en",
        attribution="Source: European Commission, Weekly Oil Bulletin",
    )


def pellets() -> PriceSeries:
    """Monthly pellet prices."""
    return PriceSeries(
        points=[(date(2026, month, 1), 400.0 + month * 5) for month in range(1, 11)],
        source="DEPI Pelletpreis",
        source_url="https://www.depi.de/pelletpreis-wirtschaftlichkeit/",
        attribution="Quelle: Deutsches Pelletinstitut GmbH (DEPI)",
        extra={"region": "national", "quantity_t": 6, "history_scope": "national"},
    )


def natural_gas() -> PriceSeries:
    """Estimated monthly gas prices."""
    return PriceSeries(
        points=[(date(2026, month, 1), 11.6 - month * 0.02) for month in range(1, 10)],
        source="Eurostat",
        source_url="https://ec.europa.eu/eurostat/databrowser/view/nrg_pc_202/default/table",
        attribution="Source: Eurostat (nrg_pc_202, prc_hicp_minr), CC BY 4.0",
        estimated=True,
        extra={"official_price": 11.56, "official_period": "2026-S1"},
    )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from custom_components."""


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Replace the network client in the coordinator and the config flow."""
    with (
        patch(
            "custom_components.heating_prices.coordinator.PriceClient", autospec=True
        ) as client_class,
        patch(
            "custom_components.heating_prices.config_flow.PriceClient", new=client_class
        ),
    ):
        client = client_class.return_value
        client.heating_oil_latest.return_value = oil_latest()
        client.heating_oil_history.return_value = oil_history()
        client.pellets.return_value = pellets()
        client.natural_gas.return_value = natural_gas()
        yield client


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """An entry for Germany with all fuels."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Deutschland",
        unique_id="DE",
        data={
            CONF_COUNTRY: "DE",
            CONF_FUELS: [FUEL_OIL, FUEL_PELLETS, FUEL_GAS],
            CONF_PELLET_REGION: "national",
            CONF_PELLET_QUANTITY: "6",
            CONF_GAS_BAND: "D2",
        },
    )
