"""Test fixtures for ELM327 OBD-II BLE integration tests."""

from typing import Any
from unittest.mock import MagicMock, patch

import obdii  # noqa: F401  # pre-cache upstream before uops shadows it
import pytest

from homeassistant.components.elm327_obdii_ble.const import DOMAIN
from homeassistant.components.elm327_obdii_ble.coordinator import Elm327ObdiiCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Return a mock ConfigEntry with default data + options."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test-entry-id"
    entry.unique_id = "AA:BB:CC:DD:EE:FF"
    entry.title = "Test OBD Adapter"
    entry.domain = DOMAIN
    entry.version = 1
    entry.data = {
        "address": "AA:BB:CC:DD:EE:FF",
        "atrv_supported": True,
        "uuid_read": "0000fff1-0000-1000-8000-00805f9b34fb",
        "uuid_write": "0000fff2-0000-1000-8000-00805f9b34fb",
    }
    entry.options = {
        "profile": {
            "standard_pids": ["ENGINE_SPEED", "VEHICLE_SPEED"],
            "custom_pids": [],
        },
        "voltage_check": True,
        "fast_poll": 5,
        "slow_poll": 300,
        "xs_poll": 3600,
        "voltage_on_threshold": 13.1,
        "voltage_off_threshold": 12.8,
        "voltage_grace_seconds": 30,
    }
    entry.runtime_data = None
    return entry


@pytest.fixture
def mock_ble_device() -> MagicMock:
    """Return a mock BLEDevice."""
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = "Test OBD Adapter"
    return device


@pytest.fixture
def mock_connection() -> MagicMock:
    """Return a mock obdii.Connection that returns canned responses."""
    conn = MagicMock()
    conn.is_connected.return_value = True
    conn.close = MagicMock()

    def _query(command: Any) -> MagicMock:
        resp = MagicMock()
        resp.raw = b"7E8 05 41 00 BE 3F A8 13\r\r>"
        resp.value = None
        resp.unparsed = []
        return resp

    conn.query = MagicMock(side_effect=_query)
    return conn


@pytest.fixture
def mock_transport() -> MagicMock:
    """Return a mock BLE transport."""
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.config = {
        "uuid_write": "0000fff2-0000-1000-8000-00805f9b34fb",
        "uuid_read": "0000fff1-0000-1000-8000-00805f9b34fb",
    }
    transport.write_bytes = MagicMock()
    transport.read_bytes = MagicMock(return_value=b"OK\r\r>")
    return transport


@pytest.fixture
def mock_coordinator(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_connection: MagicMock,
    mock_ble_device: MagicMock,
) -> Elm327ObdiiCoordinator:
    """Return a coordinator with mocked BLE + connection."""
    with (
        patch(
            "homeassistant.components.elm327_obdii_ble.coordinator.create_connection",
            return_value=mock_connection,
        ),
        patch(
            "homeassistant.components.elm327_obdii_ble.coordinator.async_address_present",
            return_value=True,
        ),
        patch(
            "homeassistant.components.elm327_obdii_ble.coordinator.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
    ):
        coord = Elm327ObdiiCoordinator(hass, mock_config_entry)
        mock_config_entry.runtime_data = coord
        return coord
