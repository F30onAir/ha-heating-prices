"""Sensors for heating oil, wood pellet, natural gas and LPG prices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    COMPARABLE_FUELS,
    CONF_LAST_PURCHASES,
    CONSUMPTION_UNITS,
    DOMAIN,
    FUEL_UNITS,
    RATINGS,
    UNIT_HEAT,
)
from .coordinator import HeatingPricesConfigEntry, HeatingPricesCoordinator
from .models import AnnualCosts, FuelPrice, PurchaseComparison
from .websocket import cheapest_fuel

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FuelSensorDescription(SensorEntityDescription):
    """Describes a sensor that shows one aspect of a fuel price."""

    value_fn: Callable[[FuelPrice], StateType]


DESCRIPTIONS: tuple[FuelSensorDescription, ...] = (
    FuelSensorDescription(
        key="price",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda price: price.price,
    ),
    FuelSensorDescription(
        key="heat_price",
        translation_key="heat_price",
        native_unit_of_measurement=UNIT_HEAT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda price: price.heat_price,
    ),
    FuelSensorDescription(
        key="change",
        translation_key="change",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda price: price.change_pct,
    ),
    FuelSensorDescription(
        key="rating",
        translation_key="rating",
        device_class=SensorDeviceClass.ENUM,
        options=list(RATINGS),
        value_fn=lambda price: price.rating,
    ),
)


@dataclass(frozen=True, kw_only=True)
class CostSensorDescription(SensorEntityDescription):
    """Describes a sensor derived from the yearly cost comparison."""

    value_fn: Callable[[AnnualCosts], int | None]


COMPARISON_COST_DESCRIPTIONS: tuple[CostSensorDescription, ...] = (
    CostSensorDescription(
        key="current_annual_cost",
        translation_key="current_annual_cost",
        value_fn=lambda costs: costs.current_cost,
    ),
    CostSensorDescription(
        key="potential_savings",
        translation_key="potential_savings",
        value_fn=lambda costs: costs.savings,
    ),
)


@dataclass(frozen=True, kw_only=True)
class PurchaseSensorDescription(SensorEntityDescription):
    """Describes a sensor that compares the last purchase with today's price."""

    value_fn: Callable[[PurchaseComparison], float]


PURCHASE_DESCRIPTIONS: tuple[PurchaseSensorDescription, ...] = (
    PurchaseSensorDescription(
        key="purchase_difference",
        translation_key="purchase_difference",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        suggested_display_precision=0,
        value_fn=lambda purchase: purchase.difference,
    ),
    PurchaseSensorDescription(
        key="purchase_change",
        translation_key="purchase_change",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda purchase: purchase.change_pct,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeatingPricesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for every enabled fuel."""
    coordinator = entry.runtime_data
    comparable = coordinator.comparable_fuels
    entities: list[SensorEntity] = []
    for fuel in coordinator.fuels:
        for description in DESCRIPTIONS:
            if description.key == "heat_price" and fuel not in COMPARABLE_FUELS:
                continue
            # The price sensor gets a per-fuel unit, name and icon.
            fuel_description = (
                replace(
                    description,
                    translation_key=f"{fuel}_price",
                    native_unit_of_measurement=FUEL_UNITS[fuel],
                )
                if description.key == "price"
                else description
            )
            entities.append(FuelSensor(coordinator, fuel, fuel_description))
        if fuel in coordinator.settings.get(CONF_LAST_PURCHASES, {}):
            entities.extend(
                PurchaseSensor(coordinator, fuel, description)
                for description in PURCHASE_DESCRIPTIONS
            )
    if len(comparable) > 1:
        entities.append(CheapestFuelSensor(coordinator))

    # Cost sensors only make sense once the user entered their consumption.
    if coordinator.annual_costs is not None:
        for fuel in comparable:
            entities.append(
                CostSensor(
                    coordinator,
                    fuel,
                    CostSensorDescription(
                        key="annual_cost",
                        translation_key="annual_cost",
                        value_fn=lambda costs, fuel=fuel: costs.costs.get(fuel),
                    ),
                )
            )
        if len(comparable) > 1:
            entities.extend(
                CostSensor(coordinator, "comparison", description)
                for description in COMPARISON_COST_DESCRIPTIONS
            )
    _async_remove_stale_entities(hass, entry, entities)
    async_add_entities(entities)


@callback
def _async_remove_stale_entities(
    hass: HomeAssistant, entry: HeatingPricesConfigEntry, entities: list[SensorEntity]
) -> None:
    """Remove what the options no longer provide, such as a deselected fuel."""
    expected = {entity.unique_id for entity in entities}
    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if entity_entry.unique_id not in expected:
            entity_registry.async_remove(entity_entry.entity_id)

    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if not er.async_entries_for_device(
            entity_registry, device.id, include_disabled_entities=True
        ):
            device_registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )


class HeatingPricesEntity(CoordinatorEntity[HeatingPricesCoordinator]):
    """Common base for all entities of this integration."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HeatingPricesCoordinator, device: str) -> None:
        """Attach the entity to one service device per fuel."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{device}")},
            translation_key=device,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Heating Prices",
            model=coordinator.country,
        )


class FuelSensor(HeatingPricesEntity, SensorEntity):
    """One value of a fuel price."""

    entity_description: FuelSensorDescription
    _unrecorded_attributes = frozenset({"source", "source_url", "region", "quantity_t"})

    def __init__(
        self,
        coordinator: HeatingPricesCoordinator,
        fuel: str,
        description: FuelSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, fuel)
        self.fuel = fuel
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{fuel}_{description.key}"
        )

    @property
    def _price(self) -> FuelPrice | None:
        return (self.coordinator.data or {}).get(self.fuel)

    @property
    def available(self) -> bool:
        """Available while there is a price for this fuel."""
        return super().available and self._price is not None

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        price = self._price
        return self.entity_description.value_fn(price) if price else None

    @property
    def attribution(self) -> str | None:
        """Credit the data source as its license requires."""
        price = self._price
        return price.attribution if price else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Context for the main price sensor."""
        price = self._price
        if price is None:
            return None
        if self.entity_description.key == "rating":
            # Lets automations (e.g. the price alert blueprint) quote the price.
            return {
                "price": price.price,
                "unit": price.unit,
                "period": price.period.isoformat(),
            }
        if self.entity_description.key != "price":
            return None
        attributes: dict[str, Any] = {
            "period": price.period.isoformat(),
            "previous_price": price.previous_price,
            "change_pct": price.change_pct,
            "min_12m": price.min_12m,
            "max_12m": price.max_12m,
            "avg_12m": price.avg_12m,
            "rating": price.rating,
            "estimated": price.estimated,
            "stale": price.stale,
            "source": price.source,
            "source_url": price.source_url,
        }
        attributes.update(price.extra)
        own_price = self.coordinator.own_price(self.fuel)
        if own_price:
            attributes["own_price"] = own_price
            attributes["own_diff_pct"] = round(
                (own_price - price.price) / price.price * 100, 1
            )
        return attributes


class CheapestFuelSensor(HeatingPricesEntity, SensorEntity):
    """Which enabled fuel gives the cheapest kWh of heat right now."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_translation_key = "cheapest_fuel"

    def __init__(self, coordinator: HeatingPricesCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "comparison")
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_cheapest_fuel"
        self._attr_options = coordinator.comparable_fuels

    @property
    def native_value(self) -> str | None:
        """Return the cheapest fuel."""
        return cheapest_fuel(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Heat price of every comparable fuel in ct/kWh."""
        return {
            f"{fuel}_heat_price": price.heat_price
            for fuel, price in (self.coordinator.data or {}).items()
            if price.heat_price is not None
        }


class CostSensor(HeatingPricesEntity, SensorEntity):
    """Yearly heating costs in euro for the user's consumption."""

    entity_description: CostSensorDescription
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR"
    _attr_suggested_display_precision = 0

    def __init__(
        self,
        coordinator: HeatingPricesCoordinator,
        device: str,
        description: CostSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{device}_{description.key}"
        )

    @property
    def native_value(self) -> int | None:
        """Return the cost."""
        costs = self.coordinator.annual_costs
        return self.entity_description.value_fn(costs) if costs else None

    @property
    def available(self) -> bool:
        """Available while the cost can be calculated."""
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Explain what the comparison is based on."""
        costs = self.coordinator.annual_costs
        if costs is None or self.entity_description.key == "annual_cost":
            return None
        return {
            "current_fuel": costs.current_fuel,
            "annual_consumption": costs.consumption,
            "consumption_unit": CONSUMPTION_UNITS[costs.current_fuel],
            "heat_demand_kwh": round(costs.heat_kwh),
            "cheapest_fuel": costs.cheapest,
        }


class PurchaseSensor(HeatingPricesEntity, SensorEntity):
    """How today's price compares with the last purchase of a fuel."""

    entity_description: PurchaseSensorDescription

    def __init__(
        self,
        coordinator: HeatingPricesCoordinator,
        fuel: str,
        description: PurchaseSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, fuel)
        self.fuel = fuel
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{fuel}_{description.key}"
        )

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        purchase = self.coordinator.last_purchase(self.fuel)
        return self.entity_description.value_fn(purchase) if purchase else None

    @property
    def available(self) -> bool:
        """Available while the purchase can be compared."""
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """The purchase and what the same amount costs today."""
        purchase = self.coordinator.last_purchase(self.fuel)
        return purchase.as_dict() if purchase else None
