"""The integration setup."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DEFAULT_TCP_PORT
from .coordinator import SolisConfigEntry, SolisDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SolisConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    # the coordinator listens for packets and holds the parsed data
    port = entry.options.get("port", DEFAULT_TCP_PORT)
    coordinator = SolisDataUpdateCoordinator(hass, entry, port=port)

    # start the listener in background
    await coordinator.async_start()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolisConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # stop listener/coordinator
        await entry.runtime_data.async_stop()

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: SolisConfigEntry) -> bool:
    """Migrate an old config entry."""
    if entry.version > 1:
        # created by a newer version of the integration, can't downgrade
        return False

    if entry.minor_version < 2:
        # The "Cumulative Production" sensor key used to be misspelled
        # ("csolis_client_umulative_production_active"). Keep existing entities
        # (and their history) by moving their unique_id to the corrected key.
        old_unique_id = f"{entry.entry_id}_csolis_client_umulative_production_active"
        new_unique_id = f"{entry.entry_id}_solis_client_cumulative_production_active"

        @callback
        def _fix_unique_id(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
            if entity_entry.unique_id == old_unique_id:
                return {"new_unique_id": new_unique_id}
            return None

        await er.async_migrate_entries(hass, entry.entry_id, _fix_unique_id)
        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True
