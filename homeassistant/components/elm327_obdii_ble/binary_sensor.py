"""Diagnostic binary sensors for the ELM327 OBD-II BLE integration."""

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import Elm327ObdiiCoordinator
from .entity import Elm327ObdiiEntity

if TYPE_CHECKING:
    from . import Elm327ObdiiConfigEntry

PARALLEL_UPDATES: Final[int] = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Elm327ObdiiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = entry.runtime_data

    entities = [
        Elm327ObdiiBinarySensor(
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
        Elm327ObdiiBinarySensor(
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


class Elm327ObdiiBinarySensor(Elm327ObdiiEntity, BinarySensorEntity):
    """Diagnostic binary sensor backed by a coordinator property callable."""

    def __init__(
        self,
        coordinator: Elm327ObdiiCoordinator,
        config_entry: Elm327ObdiiConfigEntry,
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
