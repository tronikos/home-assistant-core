"""Test the elm327_obdii_ble coordinator."""

from unittest.mock import patch

from bleak.exc import BleakError
import pytest

from homeassistant.components.elm327_obdii_ble.const import (
    FAST_POLL_SECONDS,
    OUT_OF_RANGE_POLL_SECONDS,
    SLOW_POLL_SECONDS,
)
from homeassistant.components.elm327_obdii_ble.elm327_obdii import (
    PollingState,
    PollResult,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import ELM327_SERVICE_INFO
from .conftest import (
    mock_poller_car_off,
    mock_poller_car_on,
    mock_poller_transport_error,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

DOMAIN = "elm327_obdii_ble"


async def test_coordinator_polling_intervals(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that polling intervals map correctly to states."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    assert coordinator._interval_for_state(PollingState.CAR_ON) == FAST_POLL_SECONDS
    assert coordinator._interval_for_state(PollingState.CAR_OFF) == SLOW_POLL_SECONDS
    assert (
        coordinator._interval_for_state(PollingState.OUT_OF_RANGE)
        == OUT_OF_RANGE_POLL_SECONDS
    )
    assert (
        coordinator._interval_for_state(PollingState.GRACE_PERIOD) == FAST_POLL_SECONDS
    )


async def test_coordinator_transport_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles transport errors gracefully.

    The transport error is caught by poll_once and surfaces as
    UpdateFailed, not setup failure. The coordinator still reaches
    LOADED state.
    """
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_transport_error():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    coordinator = mock_config_entry.runtime_data
    assert coordinator is not None


async def test_coordinator_ble_device_tracking(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator tracks BLE device from advertisements."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator._ble_device is not None
    assert coordinator._ble_device.address == "AA:BB:CC:DD:EE:FF"


async def test_coordinator_disconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator disconnect on unload."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on() as poller:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    poller.disconnect.assert_called_once()


async def test_coordinator_car_off_data_preservation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that car-off state preserves last known data."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.data is not None
    assert coordinator.data.get("FUEL_TYPE") == "Gasoline"

    # Now poll with car off — data should be preserved
    with mock_poller_car_off():
        coordinator._poller.poll_once.return_value = PollResult(
            state=PollingState.CAR_OFF,
            data={},
            any_success=False,
            voltage=12.0,
        )
        await coordinator._async_poll()
        await hass.async_block_till_done()

    assert coordinator.data is not None
    assert coordinator.data.get("FUEL_TYPE") == "Gasoline"


async def test_coordinator_scan_supported_pids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the scan_supported_standard_pids method."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on() as poller:
        poller.scan_supported_standard_pids.return_value = [
            "FUEL_TYPE",
            "ENGINE_SPEED",
        ]
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    result = await coordinator.async_scan_supported_standard_pids()
    assert result == ["FUEL_TYPE", "ENGINE_SPEED"]


async def test_coordinator_scan_adapter_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test scan_supported_standard_pids raises when adapter not found."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator._ble_device = None

    with (
        patch(
            "homeassistant.components.elm327_obdii_ble.coordinator.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator.async_scan_supported_standard_pids()


async def test_coordinator_scan_connect_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test scan_supported_standard_pids raises when connect fails."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on() as poller:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator._ble_device = None
    poller.is_connected = False
    poller.connect.return_value = False

    with (
        patch(
            "homeassistant.components.elm327_obdii_ble.coordinator.async_ble_device_from_address",
            return_value=ELM327_SERVICE_INFO.device,
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator.async_scan_supported_standard_pids()


async def test_coordinator_handle_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _async_handle_unavailable sets OUT_OF_RANGE and disconnects."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on() as poller:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.polling_state == PollingState.CAR_ON

    # Simulate device going unavailable
    coordinator._async_handle_unavailable(ELM327_SERVICE_INFO)
    await hass.async_block_till_done()

    assert coordinator.polling_state == PollingState.OUT_OF_RANGE
    poller.disconnect.assert_called_once()


async def test_coordinator_transport_error_after_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test transport error after a successful poll logs the warning."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    # First: successful poll (sets _was_unavailable = False)
    with mock_poller_car_on() as poller:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator._was_unavailable is False

    # Second: transport error (should log warning, set _was_unavailable = True)
    # Modify the existing poller mock — don't use a new context manager
    # because the coordinator holds a reference to the original mock instance.
    poller.poll_once.side_effect = BleakError("disconnected")
    with pytest.raises(UpdateFailed):
        await coordinator._async_update(ELM327_SERVICE_INFO)

    assert coordinator._was_unavailable is True
