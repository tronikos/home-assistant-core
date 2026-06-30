"""Diagnostic binary sensors for Universal OBD BLE.

Unchanged in behavior from the pre-refactor version — surfaces two
diagnostic connectivity sensors (BLE link up, vehicle responding).
"""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import UniversalObdCoordinator
from .entity import UniversalObdEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator: UniversalObdCoordinator = entry.runtime_data

    entities = [
        UniversalObdBleBinarySensor(
            coordinator,
            entry,
            BinarySensorEntityDescription(
                key="ble_connected",
                name="BLE Connected",
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            lambda: coordinator.ble_connected,
        ),
        UniversalObdBleBinarySensor(
            coordinator,
            entry,
            BinarySensorEntityDescription(
                key="car_connected",
                name="Car Connected",
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            lambda: coordinator.car_connected,
        ),
    ]

    async_add_entities(entities)


class UniversalObdBleBinarySensor(UniversalObdEntity, BinarySensorEntity):
    """Diagnostic binary sensor backed by a coordinator property callable."""

    def __init__(
        self,
        coordinator: UniversalObdCoordinator,
        config_entry: ConfigEntry,
        description: BinarySensorEntityDescription,
        is_on_fn,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, config_entry)
        self.entity_description = description
        self._is_on_fn = is_on_fn
        self._attr_unique_id = (
            f"{config_entry.unique_id}-binary_sensor-{description.key}"
        )

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return bool(self._is_on_fn())
