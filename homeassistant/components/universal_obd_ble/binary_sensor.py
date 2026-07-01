"""Diagnostic binary sensors for Universal OBD BLE."""

from collections.abc import Callable
import logging
from typing import Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UniversalObdConfigEntry
from .coordinator import UniversalObdCoordinator
from .entity import UniversalObdEntity

PARALLEL_UPDATES: Final[int] = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UniversalObdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = entry.runtime_data

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
        config_entry: UniversalObdConfigEntry,
        description: BinarySensorEntityDescription,
        is_on_fn: Callable[[], bool],
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
