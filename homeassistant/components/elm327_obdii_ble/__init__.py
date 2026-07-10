"""Set up the ELM327 OBD-II BLE integration."""

from typing import Final

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import Elm327ObdiiCoordinator

type Elm327ObdiiConfigEntry = ConfigEntry[Elm327ObdiiCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: Elm327ObdiiConfigEntry) -> bool:
    """Set up this integration from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper())

    coordinator = Elm327ObdiiCoordinator(hass, entry, ble_device)
    entry.runtime_data = coordinator

    entry.async_on_unload(coordinator.async_start())
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def update_options_listener(
        hass: HomeAssistant, entry: Elm327ObdiiConfigEntry
    ) -> None:
        """Reload the config entry when options change."""
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(update_options_listener))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: Elm327ObdiiConfigEntry
) -> bool:
    """Handle removal of a config entry."""
    unloaded: Final = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = entry.runtime_data
        await hass.async_add_executor_job(coordinator.disconnect)
    return unloaded
