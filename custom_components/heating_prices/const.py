"""Constants for the Heating Prices integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "heating_prices"
VERSION: Final = "1.0.2"

PROJECT_URL: Final = "https://github.com/F30onAir/ha-heating-prices"
USER_AGENT: Final = f"HomeAssistant-HeatingPrices/{VERSION} (+{PROJECT_URL})"
# Lets the project stop the TECSON requests of all installations.
SOURCES_URL: Final = (
    "https://raw.githubusercontent.com/F30onAir/ha-heating-prices/main/sources.json"
)

UPDATE_INTERVAL: Final = timedelta(hours=6)
# The full EU oil price history is large (~4.5 MB), so it is only re-read monthly.
OIL_HISTORY_MAX_AGE: Final = timedelta(days=30)
# TECSON only publishes its daily heating oil price for Germany.
DAILY_OIL_COUNTRY: Final = "DE"
# Without a newer value the daily price is of no use anymore.
DAILY_OIL_MAX_AGE: Final = timedelta(days=7)

CONF_COUNTRY: Final = "country"
CONF_FUELS: Final = "fuels"
CONF_PELLET_REGION: Final = "pellet_region"
CONF_PELLET_QUANTITY: Final = "pellet_quantity"
CONF_GAS_BAND: Final = "gas_band"
CONF_OWN_OIL_PRICE: Final = "own_oil_price"
CONF_OWN_PELLET_PRICE: Final = "own_pellet_price"
CONF_OWN_GAS_PRICE: Final = "own_gas_price"
CONF_CURRENT_FUEL: Final = "current_fuel"
CONF_ANNUAL_CONSUMPTION: Final = "annual_consumption"
CONF_LAST_PURCHASES: Final = "last_purchases"
CONF_PURCHASE_DATE: Final = "date"
CONF_PURCHASE_AMOUNT: Final = "amount"
CONF_PURCHASE_TOTAL: Final = "total_price"

FUEL_OIL: Final = "heating_oil"
FUEL_PELLETS: Final = "pellets"
FUEL_GAS: Final = "natural_gas"
FUEL_LPG: Final = "lpg"
FUELS: Final = (FUEL_OIL, FUEL_PELLETS, FUEL_GAS, FUEL_LPG)
# The official LPG price is for motor fuel (Autogas), which is taxed differently
# from LPG for heating, so it stays out of the heating cost comparison.
COMPARABLE_FUELS: Final = (FUEL_OIL, FUEL_PELLETS, FUEL_GAS)
# Fuels published in the EU Weekly Oil Bulletin, read from one history file.
BULLETIN_FUELS: Final = (FUEL_OIL, FUEL_LPG)

OWN_PRICE_KEYS: Final = {
    FUEL_OIL: CONF_OWN_OIL_PRICE,
    FUEL_PELLETS: CONF_OWN_PELLET_PRICE,
    FUEL_GAS: CONF_OWN_GAS_PRICE,
}

UNIT_OIL: Final = "€/100 L"
UNIT_PELLETS: Final = "€/t"
UNIT_GAS: Final = "ct/kWh"
UNIT_LPG: Final = "€/100 L"
UNIT_HEAT: Final = "ct/kWh"

FUEL_UNITS: Final = {
    FUEL_OIL: UNIT_OIL,
    FUEL_PELLETS: UNIT_PELLETS,
    FUEL_GAS: UNIT_GAS,
    FUEL_LPG: UNIT_LPG,
}

# Units of the amounts a user enters: yearly consumption and last purchase.
CONSUMPTION_UNITS: Final = {
    FUEL_OIL: "L",
    FUEL_PELLETS: "t",
    FUEL_GAS: "kWh",
    FUEL_LPG: "L",
}

# From € per amount above to the fuel's price unit, e.g. €/L to €/100 L.
PRICE_FACTORS: Final = {
    FUEL_OIL: 100,
    FUEL_PELLETS: 1,
    FUEL_GAS: 100,
    FUEL_LPG: 100,
}

FUEL_ICONS: Final = {
    FUEL_OIL: "mdi:oil",
    FUEL_PELLETS: "mdi:grain",
    FUEL_GAS: "mdi:fire",
    FUEL_LPG: "mdi:gas-cylinder",
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
