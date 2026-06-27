"""Common parent class representation for dynamic OBD sensor entities."""

import logging

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UniversalObdCoordinator

_LOGGER = logging.getLogger(__name__)


class UniversalObdEntity(CoordinatorEntity[UniversalObdCoordinator]):
    """Base OBD BLE dynamic entity wrapper."""

    def __init__(self, coordinator: UniversalObdCoordinator, config_entry) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Link dynamic entities cleanly to a centralized Bluetooth device entry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.unique_id)},
            connections={(CONNECTION_BLUETOOTH, self.config_entry.unique_id)},
            name=self.config_entry.title,
            manufacturer="Universal OBD BLE",
            model="ELM327 BLE Adapter",
        )
