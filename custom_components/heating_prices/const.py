"""Constants for the Heating Prices integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "heating_prices"
VERSION: Final = "0.1.3"

PROJECT_URL: Final = "https://github.com/F30onAir/ha-heating-prices"
USER_AGENT: Final = f"HomeAssistant-HeatingPrices/{VERSION} (+{PROJECT_URL})"

UPDATE_INTERVAL: Final = timedelta(hours=6)
# The full EU oil price history is large (~4.5 MB), so it is only re-read monthly.
OIL_HISTORY_MAX_AGE: Final = timedelta(days=30)

CONF_COUNTRY: Final = "country"
CONF_FUELS: Final = "fuels"
CONF_PELLET_REGION: Final = "pellet_region"
CONF_PELLET_QUANTITY: Final = "pellet_quantity"
CONF_GAS_BAND: Final = "gas_band"
CONF_OWN_OIL_PRICE: Final = "own_oil_price"
CONF_OWN_PELLET_PRICE: Final = "own_pellet_price"
CONF_OWN_GAS_PRICE: Final = "own_gas_price"

FUEL_OIL: Final = "heating_oil"
FUEL_PELLETS: Final = "pellets"
FUEL_GAS: Final = "natural_gas"
FUELS: Final = (FUEL_OIL, FUEL_PELLETS, FUEL_GAS)

OWN_PRICE_KEYS: Final = {
    FUEL_OIL: CONF_OWN_OIL_PRICE,
    FUEL_PELLETS: CONF_OWN_PELLET_PRICE,
    FUEL_GAS: CONF_OWN_GAS_PRICE,
}

UNIT_OIL: Final = "€/100 L"
UNIT_PELLETS: Final = "€/t"
UNIT_GAS: Final = "ct/kWh"
UNIT_HEAT: Final = "ct/kWh"

FUEL_UNITS: Final = {
    FUEL_OIL: UNIT_OIL,
    FUEL_PELLETS: UNIT_PELLETS,
    FUEL_GAS: UNIT_GAS,
}

FUEL_ICONS: Final = {
    FUEL_OIL: "mdi:oil",
    FUEL_PELLETS: "mdi:grain",
    FUEL_GAS: "mdi:fire",
}

# Typical net calorific values used to compare fuels per kWh of heat.
OIL_KWH_PER_LITRE: Final = 10.0
PELLETS_KWH_PER_KG: Final = 4.9

PELLET_REGION_NATIONAL: Final = "national"
PELLET_REGIONS: Final = (PELLET_REGION_NATIONAL, "north_east", "central", "south")
PELLET_QUANTITIES: Final = ("3", "6", "26")
# DEPI only publishes the 3 t price per region, not nationwide.
PELLET_NATIONAL_QUANTITIES: Final = ("6", "26")
DEFAULT_PELLET_QUANTITY: Final = "6"

GAS_BANDS: Final = ("d1", "d2", "d3")
DEFAULT_GAS_BAND: Final = "d2"

RATING_LOW: Final = "low"
RATING_NORMAL: Final = "normal"
RATING_HIGH: Final = "high"
RATINGS: Final = (RATING_LOW, RATING_NORMAL, RATING_HIGH)

# Countries covered by the EU Weekly Oil Bulletin and Eurostat gas prices.
SUPPORTED_COUNTRIES: Final = (
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR",
    "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI",
    "SK",
)  # fmt: skip
# DEPI pellet prices are only published for Germany.
PELLET_COUNTRIES: Final = ("DE",)
