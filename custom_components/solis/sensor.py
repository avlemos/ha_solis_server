"""Sensor platform for Solis client."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import SolisConfigEntry, SolisDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SolisSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]
    # function that returns a dict of attributes for this sensor from the coordinator data
    attributes_fn: Callable[[dict], dict] = lambda data: {}

STATUS_MAPPING = {
    0: "STANDBY",
    1: "ACTIVE",
}

ENTITIES = [
    SolisSensorEntityDescription(
        key="solis_client_current_power",
        translation_key="current_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:solar-power",
        value_fn=lambda d: d.get("current_power_apo_t1_W")
    ),
    SolisSensorEntityDescription(
        key="solis_client_dc_voltage_pv1",
        translation_key="dc_voltage_pv1",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        icon="mdi:flash",
        value_fn=lambda d: d.get("dv1")
    ),
    SolisSensorEntityDescription(
        key="solis_client_dc_voltage_pv2",
        translation_key="dc_voltage_pv2",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        icon="mdi:flash",
        value_fn=lambda d: d.get("dv2")
    ),
    SolisSensorEntityDescription(
        key="solis_client_ac_output_frequency_r",
        translation_key="ac_output_frequency_r",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        icon="mdi:sine-wave",
        value_fn=lambda d: d.get("a_fo1")
    ),
    SolisSensorEntityDescription(
        key="solis_client_total_production_hour",
        translation_key="total_production_hour",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:history",
        value_fn=lambda d: d.get("hr_ege_t1"),
    ),
    SolisSensorEntityDescription(
        key="solis_client_cumulative_production_active",
        translation_key="cumulative_production_active",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:counter",
        value_fn=lambda d: d.get("et_ge0"),
    ),
    SolisSensorEntityDescription(
        key="solis_client_temperature_inverter",
        translation_key="temperature_inverter",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
        value_fn=lambda d: d.get("inv_t0"),
    ),
    SolisSensorEntityDescription(
        key="solis_client_ac_voltage_r",
        translation_key="ac_voltage_r",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        icon="mdi:flash",
        value_fn=lambda d: d.get("av1"),
    ),
    SolisSensorEntityDescription(
        key="solis_client_inverter_status",
        translation_key="inverter_status",
        device_class=SensorDeviceClass.ENUM,
        options=["ACTIVE", "STANDBY", "FAULT"],
        value_fn=lambda d: (
            # 1. Check if the raw inverter_status is something other than 0 or 1
            "FAULT" if d.get("inverter_status") not in [0, 1, None] else (
                # 2. If it is 0/1, then apply the power-based logic
                "STANDBY" if d.get("current_power_apo_t1_W") == 0 else "ACTIVE"
            )
        ),
    ),
    SolisSensorEntityDescription(
        key="solis_client_dc_current_pv1",
        translation_key="dc_current_pv1",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-dc",
        value_fn=lambda d: d.get("dc1_current"),
    ),
    SolisSensorEntityDescription(
        key="solis_client_dc_current_pv2",
        translation_key="dc_current_pv2",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-dc",
        value_fn=lambda d: d.get("dc2_current"),
    ),
    SolisSensorEntityDescription(
        key="solis_client_dc_power_pv1",
        translation_key="dc_power_pv1",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:flash",
        value_fn=lambda d: d.get("dp1_power"),
    ),
    SolisSensorEntityDescription(
        key="solis_client_dc_power_pv2",
        translation_key="dc_power_pv2",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:flash",
        value_fn=lambda d: d.get("dp2_power"),
    ),
]


async def async_setup_entry(hass: HomeAssistant, entry: SolisConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(SolisCoordinatorSensor(coordinator, entry, desc) for desc in ENTITIES)


class SolisCoordinatorSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SolisDataUpdateCoordinator, entry: SolisConfigEntry, description: SolisSensorEntityDescription):
        super().__init__(coordinator)
        # name, unit, device/state class and icon all come from the description
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        # Device info is provided via the `device_info` property so it can
        # reflect the parsed `serialno` from the coordinator when available.

        # internal flag to avoid re-registering device multiple times
        self._device_registered = False
        self._unsub_listener = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # listen for coordinator updates so we can register real device when serial arrives
        self._unsub_listener = self.coordinator.async_add_listener(self._handle_coord_update)
        # try immediately in case serial already present
        await self._maybe_register_device()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None
        await super().async_will_remove_from_hass()

    async def _handle_coord_update(self) -> None:
        await self._maybe_register_device()

    async def _maybe_register_device(self) -> None:
        if self._device_registered:
            return
        data = self.coordinator.data or {}
        serial = data.get("serialno")
        if not serial:
            return

        # create device in device registry with the real serial
        from homeassistant.helpers import device_registry as dr, entity_registry as er

        dev_reg = dr.async_get(self.hass)
        device = dev_reg.async_get_or_create(
            config_entry_id=self._entry.entry_id,
            identifiers={(DOMAIN, str(serial))},
            name=data.get("device_name") or data.get("name") or f"Solis {serial}",
            manufacturer="Solis",
            model=data.get("model"),
        )

        # move this entity to the new device (if it was created under a different one)
        ent_reg = er.async_get(self.hass)
        ent = ent_reg.async_get(self.entity_id)
        if ent and ent.device_id != device.id:
            ent_reg.async_update_entity(ent.entity_id, new_device_id=device.id)

        # optionally update config entry unique_id to serial so entry shows serial
        try:
            self.hass.config_entries.async_update_entry(self._entry, unique_id=str(serial))
        except Exception:
            pass

        self._device_registered = True
        # no longer need the listener
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        return self.entity_description.value_fn(data)

    @property
    def device_info(self) -> DeviceInfo:
        """Return a DeviceInfo that uses parsed `serialno` when available."""
        data = self.coordinator.data or {}
        serial = data.get("serialno") or getattr(self._entry, "unique_id", None) or self._entry.entry_id
        name = data.get("device_name") or data.get("name") or getattr(self._entry, "title", None) or f"Solis {serial}"
        model = data.get("model")
        return DeviceInfo(
            identifiers={(DOMAIN, str(serial))},
            name=name,
            manufacturer="Solis",
            model=model,
        )

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        # let the description decide which attributes to expose for this entity
        try:
            return dict(self.entity_description.attributes_fn(data) or {})
        except Exception:
            _LOGGER.exception("attributes_fn failed")
            return {}