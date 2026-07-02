"""Common parent class for ELM327 OBD-II BLE entities."""

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Elm327ObdiiCoordinator

if TYPE_CHECKING:
    from . import Elm327ObdiiConfigEntry

_LOGGER = logging.getLogger(__name__)


class Elm327ObdiiEntity(CoordinatorEntity[Elm327ObdiiCoordinator]):
    """Base entity that links to the shared Bluetooth device entry."""

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
        unique_id = self.config_entry.unique_id
        return DeviceInfo(
            identifiers={(DOMAIN, unique_id)} if unique_id else set(),
            connections={(CONNECTION_BLUETOOTH, unique_id)} if unique_id else set(),
            name=self.config_entry.title,
            manufacturer="ELM327 OBD-II BLE",
            model="ELM327 BLE Adapter",
        )
