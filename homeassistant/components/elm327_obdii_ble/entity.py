"""Common parent class for ELM327 OBD-II BLE entities."""

import logging
from typing import TYPE_CHECKING

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo, format_mac

from .coordinator import Elm327ObdiiCoordinator

if TYPE_CHECKING:
    from . import Elm327ObdiiConfigEntry

_LOGGER = logging.getLogger(__name__)


class Elm327ObdiiEntity(PassiveBluetoothCoordinatorEntity[Elm327ObdiiCoordinator]):
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
        # unique_id (format_mac) is for HA config entry tracking;
        # coordinator.address is the raw address for BLE connections.
        # Both are normalized to format_mac here for the device registry.
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
    def available(self) -> bool:
        """Always available — entities retain last known value when out of range."""
        return True
