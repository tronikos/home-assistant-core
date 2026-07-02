"""Common parent class for ELM327 OBD-II BLE entities."""

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import Elm327ObdiiCoordinator

if TYPE_CHECKING:
    from . import Elm327ObdiiConfigEntry

_LOGGER = logging.getLogger(__name__)


class Elm327ObdiiEntity(CoordinatorEntity[Elm327ObdiiCoordinator]):
    """Base entity that links to the shared Bluetooth device entry.

    Uses ``connections`` only (not ``identifiers``) so the entity is
    linked to the device entry the bluetooth integration already
    created for the same MAC - no duplicate device entries.
    """

    def __init__(
        self,
        coordinator: Elm327ObdiiCoordinator,
        config_entry: Elm327ObdiiConfigEntry,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Link dynamic entities to the centralized Bluetooth device entry."""
        # __init__.py raises ConfigEntryError for missing unique_id before
        # any entity is created, so this assertion never fires in practice.
        unique_id = self.config_entry.unique_id
        assert unique_id is not None
        return DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, unique_id)},
            name=self.config_entry.title,
            manufacturer="ELM327",
            model="OBD-II BLE Adapter",
        )
