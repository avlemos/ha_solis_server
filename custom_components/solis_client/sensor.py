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
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import SolisDataUpdateCoordinator

@dataclass
class SolisSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any] = lambda data: None
    # function that returns a dict of attributes for this sensor from the coordinator data
    attributes_fn: Callable[[dict], dict] = lambda data: {}

STATUS_MAPPING = {
    0: "STANDBY",
    1: "ACTIVE",
}

ENTITIES = [
    SolisSensorEntityDescription(
        key="solis_client_current_power",
        name="Current power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        icon="mdi:solar-power",
        value_fn=lambda d: d.get("current_power_apo_t1_W")
    ),
    SolisSensorEntityDescription(
        key="solis_client_dc_voltage_pv1",
        name="DC Voltage PV1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement="V",
        icon="mdi:flash",
        value_fn=lambda d: d.get("dv1")
    ),
    SolisSensorEntityDescription(
        key="solis_client_dc_voltage_pv2",
        name="DC Voltage PV2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement="V",
        icon="mdi:flash",
        value_fn=lambda d: d.get("dv2")
    ),
    SolisSensorEntityDescription(
        key="solis_client_ac_output_frequency_r",
        name="AC Output Frequency R",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement="Hz",
        icon="mdi:sine-wave",
        value_fn=lambda d: d.get("a_fo1")
    )
    ,
    SolisSensorEntityDescription(
        key="solis_client_total_production_hour",
        name="Total Production Hour",
        native_unit_of_measurement="h",
        state_class="total_increasing",
        icon="mdi:history",
        value_fn=lambda d: (
            d.get("hr_ege_t1")
        ),
        # attributes_fn=lambda d: {"raw": d.get("hr_ege_t1_raw") or d.get("total_production_hour_hr_ege_t1_raw")},
    ),
    SolisSensorEntityDescription(
        key="csolis_client_umulative_production_active",
        name="Cumulative Production (Active)",
        device_class=SensorDeviceClass.ENERGY,
        state_class="total_increasing",
        native_unit_of_measurement="kWh",
        icon="mdi:counter",
        value_fn=lambda d: (
            d.get("et_ge0")
        )
    ),
    SolisSensorEntityDescription(
        key="solis_client_temperature_inverter",
        name="Temperature - Inverter",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
        icon="mdi:thermometer",
        value_fn=lambda d: (
            d.get("inv_t0")
        ),
        # attributes_fn=lambda d: {"raw": d.get("inv_t0_raw")},
    ),
    SolisSensorEntityDescription(
        key="solis_client_ac_voltage_r",
        name="AC Voltage R",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement="V",
        icon="mdi:flash",
        value_fn=lambda d: (
            d.get("av1")
        ),
        # attributes_fn=lambda d: {"raw": d.get("av1_raw") or d.get("AV1_raw")},
    ),
    SolisSensorEntityDescription(
        key="solis_client_inverter_status",
        name="Inverter Status",
        device_class=SensorDeviceClass.ENUM,
        options=["ACTIVE", "STANDBY"],
        value_fn=lambda d: STATUS_MAPPING.get(d.get("inverter_status"), "UNKNOWN")
    ),
    SolisSensorEntityDescription(
        key="solis_client_dc_current_pv1",
        name="DC Current PV1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement="A",
        icon="mdi:current-dc",
        value_fn=lambda d: (d.get("dc1_current") ),
        # attributes_fn=lambda d: {"raw": d.get("dc1_raw") or d.get("DC1_raw")},
    ),
    SolisSensorEntityDescription(
        key="solis_client_dc_current_pv2",
        name="DC Current PV2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement="A",
        icon="mdi:current-dc",
        value_fn=lambda d: (d.get("dc2_current")),
        # attributes_fn=lambda d: {"raw": d.get("dc2_raw") or d.get("DC2_raw")},
    ),
    SolisSensorEntityDescription(
        key="solis_client_dc_power_pv1",
        name="DC Power PV1",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        icon="mdi:flash",
        value_fn=lambda d: (d.get("dp1_power")),
        # attributes_fn=lambda d: {"raw": d.get("dp1_raw") or d.get("DP1_raw")},
    ),
    SolisSensorEntityDescription(
        key="solis_client_dc_power_pv2",
        name="DC Power PV2",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        icon="mdi:flash",
        value_fn=lambda d: (d.get("dp2_power")),
        # attributes_fn=lambda d: {"raw": d.get("dp2_raw") or d.get("DP2_raw")},
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

        # Device info is provided via the `device_info` property so it can
        # reflect the parsed `serialno` from the coordinator when available.

        # expose device info from the description so HA picks up unit, device class and icon
        if description.device_class:
            self._attr_device_class = description.device_class
        if description.native_unit_of_measurement:
            self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        if description.icon:
            self._attr_icon = description.icon
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
            _LOGGER = __import__("logging").getLogger(__name__)
            _LOGGER.exception("attributes_fn failed")
            return {}