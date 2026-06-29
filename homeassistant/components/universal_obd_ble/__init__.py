"""Initializes and unloads the Universal OBD BLE config entries."""

import contextlib
import logging
import time
from typing import Final

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError

from .const import DEBOUNCE_COOLDOWN, DOMAIN, PLATFORMS
from .coordinator import UniversalObdCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    if not entry.unique_id:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="missing_unique_id",
        )

    coordinator = UniversalObdCoordinator(hass, entry)
    entry.runtime_data = coordinator

    # Ensure entities populate with initial state at startup before forwarding setup
    # Suppress exceptions so entities still register (as unavailable) if the car is currently off/out-of-range.
    with contextlib.suppress(Exception):
        await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _async_specific_device_found(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle re-discovery of the device to query immediately upon arrival."""
        _LOGGER.debug("Target device back in range: %s", service_info.address)

        now = time.monotonic()

        # Debounce to prevent constant connection loops from BLE advertisement storms
        # utilizing the timestamp of the last actual attempt (not just successful polls)
        if (now - coordinator.last_discovery_attempt) > DEBOUNCE_COOLDOWN:
            coordinator.last_discovery_attempt = now
            _LOGGER.debug("Initiating debounced arrival update for coordinator")
            hass.async_create_task(coordinator.async_request_refresh())

    # Active Scanning Mode Gating
    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_specific_device_found,
            {"address": entry.data[CONF_ADDRESS]},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    async def update_options_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Reload configuration on update."""
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(update_options_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry cleanly."""
    unloaded: Final = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = entry.runtime_data
        # Safely delegate disconnection to the thread pool to execute the synchronous close,
        # unblocking any threads waiting on `self._data_ready.wait()`
        await hass.async_add_executor_job(coordinator.disconnect)
    return unloaded
