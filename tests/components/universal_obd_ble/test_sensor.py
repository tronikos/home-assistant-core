"""Tests for the Universal OBD BLE sensor platform."""

from unittest.mock import MagicMock

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.universal_obd_ble.sensor import (
    UniversalObdCustomSensor,
    UniversalObdStandardSensor,
)
from homeassistant.components.universal_obd_ble.uops import (
    CustomPid,
    format_sensor_value,
)
from homeassistant.core import HomeAssistant


def test_format_sensor_value_none() -> None:
    """Test that None is returned as-is."""
    assert format_sensor_value(None) is None


def test_format_sensor_value_float() -> None:
    """Test that floats are returned as-is."""
    assert format_sensor_value(42.5) == 42.5


def test_format_sensor_value_int() -> None:
    """Test that ints are returned as-is."""
    assert format_sensor_value(42) == 42


def test_format_sensor_value_str() -> None:
    """Test that strings are returned as-is."""
    assert format_sensor_value("hello") == "hello"


def test_format_sensor_value_list() -> None:
    """Test that lists are joined with commas."""
    assert format_sensor_value([1, 2, 3]) == "1, 2, 3"


def test_format_sensor_value_list_of_tuples() -> None:
    """Test that list-of-tuples takes the first element of each tuple."""
    result = format_sensor_value([(1.5, "A"), (2.0, "B")])
    assert result == "1.5, 2.0"


def test_format_sensor_value_empty_list() -> None:
    """Test that empty lists produce an empty string."""
    assert format_sensor_value([]) == ""


def test_standard_sensor_initialization(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that UniversalObdStandardSensor initializes correctly."""
    coordinator = MagicMock()
    command = MagicMock()
    command.name = "ENGINE_SPEED"
    command.mode = "01"
    command.pid = "0C"
    command.units = "rpm"

    sensor = UniversalObdStandardSensor(
        coordinator, mock_config_entry, "ENGINE_SPEED", command
    )

    assert sensor._command_name == "ENGINE_SPEED"
    assert "Engine speed" in sensor._attr_name
    assert sensor._attr_unique_id == f"{mock_config_entry.unique_id}-std-engine_speed"
    assert sensor._attr_device_class == SensorDeviceClass.SPEED
    assert sensor._attr_native_unit_of_measurement == "rpm"


def test_custom_sensor_initialization(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that UniversalObdCustomSensor initializes correctly."""
    coordinator = MagicMock()
    pid = CustomPid(
        id="test-pid",
        name="Battery SOC",
        mode="22",
        query="028C1",
        formula="B(4) / 2.55",
        unit="%",
        device_class="battery",
        state_class="measurement",
        min_value=0,
        max_value=100,
    )

    sensor = UniversalObdCustomSensor(coordinator, mock_config_entry, pid)

    assert sensor._pid == pid
    assert sensor._attr_name == "Battery SOC"
    assert sensor._attr_unique_id == f"{mock_config_entry.unique_id}-custom-test-pid"
    assert sensor._attr_native_unit_of_measurement == "%"
    assert sensor._attr_extra_state_attributes == {"min_value": 0, "max_value": 100}


def test_custom_sensor_voltage_override(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that 'battery' device_class with V unit becomes VOLTAGE."""
    coordinator = MagicMock()
    pid = CustomPid(
        id="test-pid",
        name="Pack Voltage",
        mode="22",
        query="1E3B1",
        formula="B(4, 5) / 10",
        unit="V",
        device_class="battery",
    )

    sensor = UniversalObdCustomSensor(coordinator, mock_config_entry, pid)

    assert sensor._attr_device_class == SensorDeviceClass.VOLTAGE


def test_custom_sensor_native_value(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that native_value reads from coordinator data."""
    coordinator = MagicMock()
    coordinator.data = {"SOC": 75.5}

    pid = CustomPid(
        id="test-pid",
        name="SOC",
        mode="22",
        query="028C1",
        formula="B(4) / 2.55",
    )

    sensor = UniversalObdCustomSensor(coordinator, mock_config_entry, pid)
    sensor.coordinator = coordinator

    assert sensor.native_value == 75.5


def test_custom_sensor_native_value_none(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that native_value returns None when coordinator data is None."""
    coordinator = MagicMock()
    coordinator.data = None

    pid = CustomPid(
        id="test-pid",
        name="SOC",
        mode="22",
        query="028C1",
        formula="B(4) / 2.55",
    )

    sensor = UniversalObdCustomSensor(coordinator, mock_config_entry, pid)
    sensor.coordinator = coordinator

    assert sensor.native_value is None


def test_custom_sensor_odometer_state_class(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that odometer gets TOTAL_INCREASING state class."""
    coordinator = MagicMock()
    pid = CustomPid(
        id="test-odo",
        name="Odometer",
        mode="22",
        query="02BD2",
        formula="B(4, 7)",
        unit="km",
    )

    sensor = UniversalObdCustomSensor(coordinator, mock_config_entry, pid)

    assert sensor._attr_state_class == SensorStateClass.TOTAL_INCREASING
