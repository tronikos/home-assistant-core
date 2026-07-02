"""Set up the ELM327 OBD-II BLE integration."""

import logging
import time
from typing import Final

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError

from .const import DEBOUNCE_COOLDOWN, DOMAIN, PLATFORMS
from .coordinator import Elm327ObdiiCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)

type Elm327ObdiiConfigEntry = ConfigEntry[Elm327ObdiiCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: Elm327ObdiiConfigEntry) -> bool:
    """Set up this integration from a config entry."""
    if not entry.unique_id:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="missing_unique_id",
        )

    coordinator = Elm327ObdiiCoordinator(hass, entry)
    entry.runtime_data = coordinator

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

        # Debounce advertisement storms - only request a refresh if
        # we haven't attempted one in the last DEBOUNCE_COOLDOWN seconds.
        if (now - coordinator.last_rediscovery_attempt) > DEBOUNCE_COOLDOWN:
            coordinator.last_rediscovery_attempt = now
            _LOGGER.debug("Initiating debounced arrival update for coordinator")
            hass.async_create_task(coordinator.async_request_refresh())

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_specific_device_found,
            {"address": entry.data[CONF_ADDRESS]},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    async def update_options_listener(
        hass: HomeAssistant, entry: Elm327ObdiiConfigEntry
    ) -> None:
        """Reload the config entry when options change.

        A full reload creates a fresh coordinator, which rebuilds its
        query plan from the updated entry.options[CONF_PROFILE].
        """
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
        # Disconnect from the executor pool - the BLE transport's
        # close() runs synchronous I/O that can't happen on the loop.
        await hass.async_add_executor_job(coordinator.disconnect)
    return unloaded
