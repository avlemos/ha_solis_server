"""Sensor platform for Solis client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolisDataUpdateCoordinator

@dataclass
class SolisSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any] = lambda data: None
    # function that returns a dict of attributes for this sensor from the coordinator data
    attributes_fn: Callable[[dict], dict] = lambda data: {}

ENTITIES = [
    SolisSensorEntityDescription(
        key="current_power",
        name="Current power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        icon="mdi:solar-power",
        value_fn=lambda d: d.get("current_power_apo_t1_W")
    ),
    SolisSensorEntityDescription(
        key="dc_voltage_pv1",
        name="DC Voltage PV1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement="V",
        icon="mdi:flash",
        value_fn=lambda d: d.get("dv1")
    ),
    SolisSensorEntityDescription(
        key="dc_voltage_pv2",
        name="DC Voltage PV2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement="V",
        icon="mdi:flash",
        value_fn=lambda d: d.get("dv2")
    ),
    SolisSensorEntityDescription(
        key="ac_output_frequency_r",
        name="AC Output Frequency R",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement="Hz",
        icon="mdi:sine-wave",
        value_fn=lambda d: d.get("a_fo1")
    )
    ,
    SolisSensorEntityDescription(
        key="total_production_hour",
        name="Total Production Hour",
        native_unit_of_measurement="h",
        icon="mdi:history",
        value_fn=lambda d: (
            d.get("hr_ege_t1")
        ),
        # attributes_fn=lambda d: {"raw": d.get("hr_ege_t1_raw") or d.get("total_production_hour_hr_ege_t1_raw")},
    ),
    SolisSensorEntityDescription(
        key="cumulative_production_active",
        name="Cumulative Production (Active)",
        device_class=SensorDeviceClass.ENERGY,
        state_class="total_increasing",
        native_unit_of_measurement="kWh",
        icon="mdi:counter",
        value_fn=lambda d: (
            d.get("et_ge0")
        )
    ),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: SolisDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([SolisCoordinatorSensor(coordinator, entry, desc) for desc in ENTITIES], True)


class SolisCoordinatorSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator: SolisDataUpdateCoordinator, entry: ConfigEntry, description: SolisSensorEntityDescription):
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        # friendly name: use description name only (e.g. "Current power")
        self._attr_name = description.name
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        # expose device info from the description so HA picks up unit, device class and icon
        if description.device_class:
            self._attr_device_class = description.device_class
        if description.native_unit_of_measurement:
            self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        if description.icon:
            self._attr_icon = description.icon

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        return self.entity_description.value_fn(data)

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        # let the description decide which attributes to expose for this entity
        try:
            return dict(self.entity_description.attributes_fn(data) or {})
        except Exception:
            _LOGGER = __import__("logging").getLogger(__name__)
            _LOGGER.exception("attributes_fn failed")
            return {}