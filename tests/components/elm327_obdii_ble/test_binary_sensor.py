"""Tests for the ELM327 OBD-II BLE binary sensor platform."""

from unittest.mock import MagicMock

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.elm327_obdii_ble.binary_sensor import (
    Elm327ObdiiBinarySensor,
)
from homeassistant.const import EntityCategory


def test_binary_sensor_ble_connected() -> None:
    """Test the BLE connected binary sensor."""
    coordinator = MagicMock()
    coordinator.ble_connected = True

    config_entry = MagicMock()
    config_entry.unique_id = "test-unique-id"

    desc = BinarySensorEntityDescription(
        key="ble_connected",
        name="BLE Connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    sensor = Elm327ObdiiBinarySensor(
        coordinator, config_entry, desc, lambda: coordinator.ble_connected
    )

    assert sensor.is_on is True
    assert sensor.entity_description.key == "ble_connected"
    assert sensor._attr_unique_id == "test-unique-id-binary_sensor-ble_connected"


def test_binary_sensor_car_connected() -> None:
    """Test the car connected binary sensor."""
    coordinator = MagicMock()
    coordinator.car_connected = False

    config_entry = MagicMock()
    config_entry.unique_id = "test-unique-id"

    desc = BinarySensorEntityDescription(
        key="car_connected",
        name="Car Connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    sensor = Elm327ObdiiBinarySensor(
        coordinator, config_entry, desc, lambda: coordinator.car_connected
    )

    assert sensor.is_on is False
