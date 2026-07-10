"""Common parent class for ELM327 OBD-II BLE entities."""

from typing import TYPE_CHECKING, override

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import Elm327ObdiiCoordinator

if TYPE_CHECKING:
    from . import Elm327ObdiiConfigEntry


class Elm327ObdiiEntity(CoordinatorEntity[Elm327ObdiiCoordinator]):
    """Base entity that links to the shared Bluetooth device entry.

    Uses ``connections`` only (not ``identifiers``) so the entity is
    linked to the device entry the bluetooth integration already
    created for the same MAC - no duplicate device entries.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Elm327ObdiiCoordinator,
        config_entry: Elm327ObdiiConfigEntry,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        address = format_mac(coordinator.address)
        self._attr_device_info = DeviceInfo(
            connections={
                (dr.CONNECTION_BLUETOOTH, address),
                (dr.CONNECTION_NETWORK_MAC, address),
            },
            name=config_entry.title,
            manufacturer="ELM327",
            model="OBD-II BLE Adapter",
        )

    @property
    @override
    def available(self) -> bool:
        """Always available — entities retain last known value when out of range."""
        return True
