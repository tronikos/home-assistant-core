"""Tests for the Universal OBD BLE coordinator."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.universal_obd_ble.coordinator import (
    UniversalObdCoordinator,
)
from homeassistant.components.universal_obd_ble.uops import PollingState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

pytestmark = pytest.mark.asyncio


async def test_coordinator_initial_state(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that the coordinator starts in OUT_OF_RANGE state."""
    with (
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.create_connection",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.async_address_present",
            return_value=True,
        ),
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
    ):
        coord = UniversalObdCoordinator(hass, mock_config_entry)

    assert coord.state == PollingState.OUT_OF_RANGE
    assert coord.data == {}
    assert coord.consecutive_failures == 0
    assert coord.last_successful_poll is None


async def test_coordinator_ble_disconnected(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that ble_connected returns False when no API exists."""
    with (
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.create_connection",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.async_address_present",
            return_value=True,
        ),
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
    ):
        coord = UniversalObdCoordinator(hass, mock_config_entry)

    assert coord.ble_connected is False


async def test_coordinator_car_connected_false(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that car_connected is False when no successful poll has happened."""
    with (
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.create_connection",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.async_address_present",
            return_value=True,
        ),
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
    ):
        coord = UniversalObdCoordinator(hass, mock_config_entry)

    assert coord.car_connected is False


async def test_coordinator_disconnect(
    hass: HomeAssistant, mock_config_entry: MagicMock, mock_connection: MagicMock
) -> None:
    """Test that disconnect closes the API connection."""
    with (
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.create_connection",
            return_value=mock_connection,
        ),
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.async_address_present",
            return_value=True,
        ),
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
    ):
        coord = UniversalObdCoordinator(hass, mock_config_entry)
        coord.api = mock_connection
        coord._current_context = MagicMock()

        coord.disconnect()

    mock_connection.close.assert_called_once()
    assert coord.api is None
    assert coord._current_context is None


async def test_coordinator_query_plan_built(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that the coordinator builds a query plan from UOPS config."""
    with (
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.create_connection",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.async_address_present",
            return_value=True,
        ),
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
    ):
        coord = UniversalObdCoordinator(hass, mock_config_entry)

    assert len(coord._query_plan) >= 1
    total_items = sum(len(group) for _, group in coord._query_plan)
    assert total_items == 2


async def test_coordinator_update_ble_out_of_range(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that _async_update_data raises when BLE is out of range."""
    with (
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.create_connection",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.universal_obd_ble.coordinator.async_address_present",
            return_value=False,
        ),
    ):
        coord = UniversalObdCoordinator(hass, mock_config_entry)

        with pytest.raises(UpdateFailed, match="device_out_of_range"):
            await coord._async_update_data()
