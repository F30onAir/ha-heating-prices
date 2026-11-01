"""Config and options flow for Heating Prices."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    CountrySelector,
    CountrySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import voluptuous as vol

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
    FUEL_UNITS,
    FUELS,
    GAS_BANDS,
    OWN_PRICE_KEYS,
    PELLET_COUNTRIES,
    PELLET_NATIONAL_QUANTITIES,
    PELLET_QUANTITIES,
    PELLET_REGION_NATIONAL,
    PELLET_REGIONS,
    SUPPORTED_COUNTRIES,
)
from .coordinator import HeatingPricesConfigEntry
from .providers import ParseError, oil_bulletin

COUNTRY_TITLES = {
    "de": {
        "AT": "Österreich", "BE": "Belgien", "BG": "Bulgarien", "CY": "Zypern",
        "CZ": "Tschechien", "DE": "Deutschland", "DK": "Dänemark", "EE": "Estland",
        "ES": "Spanien", "FI": "Finnland", "FR": "Frankreich", "GR": "Griechenland",
        "HR": "Kroatien", "HU": "Ungarn", "IE": "Irland", "IT": "Italien",
        "LT": "Litauen", "LU": "Luxemburg", "LV": "Lettland", "MT": "Malta",
        "NL": "Niederlande", "PL": "Polen", "PT": "Portugal", "RO": "Rumänien",
        "SE": "Schweden", "SI": "Slowenien", "SK": "Slowakei",
    },
}  # fmt: skip


def _select(options: list[str] | tuple[str, ...], key: str) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=list(options), translation_key=key, mode=SelectSelectorMode.DROPDOWN
        )
    )


def _pellet_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_PELLET_REGION, default=PELLET_REGION_NATIONAL): _select(
                PELLET_REGIONS, CONF_PELLET_REGION
            ),
            vol.Required(
                CONF_PELLET_QUANTITY, default=DEFAULT_PELLET_QUANTITY
            ): _select(PELLET_QUANTITIES, CONF_PELLET_QUANTITY),
        }
    )


def _gas_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_GAS_BAND, default=DEFAULT_GAS_BAND): _select(
                GAS_BANDS, CONF_GAS_BAND
            )
        }
    )


def _pellet_errors(user_input: dict[str, Any]) -> dict[str, str]:
    if (
        user_input[CONF_PELLET_REGION] == PELLET_REGION_NATIONAL
        and user_input[CONF_PELLET_QUANTITY] not in PELLET_NATIONAL_QUANTITIES
    ):
        return {CONF_PELLET_QUANTITY: "quantity_regional_only"}
    return {}


async def _check(call: Any) -> str | None:
    """Run a source request and map failures to a form error."""
    try:
        await call
    except ParseError:
        return "no_data"
    except SOURCE_ERRORS:
        return "cannot_connect"
    return None


class HeatingPricesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up prices for one country."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: HeatingPricesConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return HeatingPricesOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the country and fuels."""
        errors: dict[str, str] = {}
        if user_input is not None:
            country = user_input[CONF_COUNTRY]
            fuels = user_input[CONF_FUELS]
            await self.async_set_unique_id(country)
            self._abort_if_unique_id_configured()
            if not fuels:
                errors[CONF_FUELS] = "no_fuels"
            elif FUEL_PELLETS in fuels and country not in PELLET_COUNTRIES:
                errors[CONF_FUELS] = "pellets_unavailable"
            elif FUEL_OIL in fuels and (
                error := await _check(
                    PriceClient(self.hass).heating_oil_latest(country)
                )
            ):
                errors["base"] = f"oil_{error}"
            else:
                self._data = dict(user_input)
                return await self._async_next_step()

        default_country = (
            self.hass.config.country
            if self.hass.config.country in SUPPORTED_COUNTRIES
            else "DE"
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_COUNTRY, default=default_country): CountrySelector(
                    CountrySelectorConfig(countries=list(SUPPORTED_COUNTRIES))
                ),
                vol.Required(CONF_FUELS, default=list(FUELS)): SelectSelector(
                    SelectSelectorConfig(
                        options=list(FUELS),
                        translation_key=CONF_FUELS,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def _async_next_step(self) -> ConfigFlowResult:
        fuels = self._data[CONF_FUELS]
        if FUEL_PELLETS in fuels and CONF_PELLET_REGION not in self._data:
            return await self.async_step_pellets()
        if FUEL_GAS in fuels and CONF_GAS_BAND not in self._data:
            return await self.async_step_gas()
        country = self._data[CONF_COUNTRY]
        titles = COUNTRY_TITLES.get(
            self.hass.config.language[:2], oil_bulletin.COUNTRY_NAMES
        )
        return self.async_create_entry(
            title=titles.get(country, country), data=self._data
        )

    async def async_step_pellets(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose region and delivery quantity for wood pellets."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _pellet_errors(user_input)
            if not errors and (
                error := await _check(
                    PriceClient(self.hass).pellets(
                        user_input[CONF_PELLET_REGION], user_input[CONF_PELLET_QUANTITY]
                    )
                )
            ):
                errors["base"] = f"pellets_{error}"
            if not errors:
                self._data.update(user_input)
                return await self._async_next_step()
        return self.async_show_form(
            step_id="pellets",
            data_schema=self.add_suggested_values_to_schema(
                _pellet_schema(), user_input
            ),
            errors=errors,
        )

    async def async_step_gas(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the annual consumption band for natural gas."""
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await _check(
                PriceClient(self.hass).natural_gas(
                    self._data[CONF_COUNTRY], user_input[CONF_GAS_BAND]
                )
            )
            if error:
                errors["base"] = f"gas_{error}"
            else:
                self._data.update(user_input)
                return await self._async_next_step()
        return self.async_show_form(
            step_id="gas",
            data_schema=self.add_suggested_values_to_schema(_gas_schema(), user_input),
            errors=errors,
        )


class HeatingPricesOptionsFlow(OptionsFlow):
    """Change own prices, pellet region and gas band."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        fuels = self.config_entry.data[CONF_FUELS]
        errors: dict[str, str] = {}
        if user_input is not None:
            if FUEL_PELLETS in fuels:
                errors = _pellet_errors(user_input)
            if not errors:
                return self.async_create_entry(data=user_input)

        fields: dict[Any, Any] = {}
        for fuel in FUELS:
            if fuel not in fuels:
                continue
            fields[vol.Optional(OWN_PRICE_KEYS[fuel])] = NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=10000,
                    step=0.01,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement=FUEL_UNITS[fuel],
                )
            )
        if FUEL_PELLETS in fuels:
            fields.update(_pellet_schema().schema)
        if FUEL_GAS in fuels:
            fields.update(_gas_schema().schema)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(fields), user_input or current
            ),
            errors=errors,
        )
