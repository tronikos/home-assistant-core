"""Diagnostics support for the ELM327 OBD-II BLE integration."""

from typing import TYPE_CHECKING, Any

from homeassistant.components import bluetooth
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from . import Elm327ObdiiConfigEntry
    from .coordinator import Elm327ObdiiCoordinator

ENTRY_TO_REDACT = frozenset({"address", "uuid_read", "uuid_write"})
SERVICE_INFO_TO_REDACT = frozenset({"address", "name", "source", "device"})


def _coordinator_diagnostics(coordinator: Elm327ObdiiCoordinator) -> dict[str, Any]:
    """Snapshot coordinator state for diagnostics."""
    return {
        "polling_state": coordinator.polling_state.value,
        "voltage": coordinator.voltage,
        "data": coordinator.data,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: Elm327ObdiiConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    service_info = bluetooth.async_last_service_info(
        hass, coordinator.address, connectable=True
    )
    return {
        "entry": async_redact_data(entry.as_dict(), ENTRY_TO_REDACT),
        "service_info": async_redact_data(
            service_info.as_dict() if service_info else None,
            SERVICE_INFO_TO_REDACT,
        ),
        "coordinator": _coordinator_diagnostics(coordinator),
    }
