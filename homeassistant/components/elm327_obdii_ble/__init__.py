"""Set up the ELM327 OBD-II BLE integration."""

from typing import Final

from bluetooth_data_tools import monotonic_time_coarse

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothReachabilityIntent,
    BluetoothScanningMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DEBOUNCE_COOLDOWN, DOMAIN, PLATFORMS
from .coordinator import Elm327ObdiiCoordinator

type Elm327ObdiiConfigEntry = ConfigEntry[Elm327ObdiiCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: Elm327ObdiiConfigEntry) -> bool:
    """Set up this integration from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address)
    if not ble_device:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={
                "address": address,
                "reason": bluetooth.async_address_reachability_diagnostics(
                    hass, address, BluetoothReachabilityIntent.CONNECTION
                ),
            },
        )

    coordinator = Elm327ObdiiCoordinator(hass, entry)
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _async_device_found(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Trigger an immediate refresh when the adapter advertises."""
        now = monotonic_time_coarse()
        if (now - coordinator.last_rediscovery_attempt) > DEBOUNCE_COOLDOWN:
            coordinator.last_rediscovery_attempt = now
            entry.async_create_background_task(
                hass,
                coordinator.async_request_refresh(),
                "elm327_obdii_ble_rediscovery_refresh",
            )

    coordinator.last_rediscovery_attempt = 0.0

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_device_found,
            {"address": entry.data[CONF_ADDRESS]},
            BluetoothScanningMode.ACTIVE,
        )
    )

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
