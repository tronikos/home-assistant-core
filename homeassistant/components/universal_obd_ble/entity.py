"""Common parent class for all Universal OBD BLE entities.

Unchanged from the pre-refactor version - links every entity to the
single Bluetooth device entry created from the config flow.
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UniversalObdCoordinator

_LOGGER = logging.getLogger(__name__)


class UniversalObdEntity(CoordinatorEntity[UniversalObdCoordinator]):
    """Base entity that links to the shared Bluetooth device entry."""

    def __init__(
        self, coordinator: UniversalObdCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Link dynamic entities to the centralized Bluetooth device entry."""
        unique_id = self.config_entry.unique_id
        return DeviceInfo(
            identifiers={(DOMAIN, unique_id)} if unique_id else set(),
            connections={(CONNECTION_BLUETOOTH, unique_id)} if unique_id else set(),
            name=self.config_entry.title,
            manufacturer="Universal OBD BLE",
            model="ELM327 BLE Adapter",
        )
