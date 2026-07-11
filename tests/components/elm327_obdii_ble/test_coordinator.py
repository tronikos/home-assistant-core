"""Test the elm327_obdii_ble coordinator."""

from datetime import timedelta
from unittest.mock import patch

from elm327_obdii import PollingState, PollResult
import pytest

from homeassistant.components.elm327_obdii_ble.const import (
    FAST_POLL_SECONDS,
    OUT_OF_RANGE_POLL_SECONDS,
    SLOW_POLL_SECONDS,
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
    """Test that update_interval adjusts based on polling state."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        await mock_config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator._update_interval_for(PollingState.CAR_ON)
    assert coordinator.update_interval == timedelta(seconds=FAST_POLL_SECONDS)
    coordinator._update_interval_for(PollingState.CAR_OFF)
    assert coordinator.update_interval == timedelta(seconds=SLOW_POLL_SECONDS)
    coordinator._update_interval_for(PollingState.OUT_OF_RANGE)
    assert coordinator.update_interval == timedelta(seconds=OUT_OF_RANGE_POLL_SECONDS)
    coordinator._update_interval_for(PollingState.GRACE_PERIOD)
    assert coordinator.update_interval == timedelta(seconds=FAST_POLL_SECONDS)


async def test_coordinator_transport_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles transport errors gracefully."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_transport_error():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    coordinator = mock_config_entry.runtime_data
    assert coordinator is not None


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
        await mock_config_entry.runtime_data.async_refresh()
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
        await mock_config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.data is not None
    assert coordinator.data.get("FUEL_LEVEL") == 75.0

    with mock_poller_car_off():
        coordinator._poller.poll_once.return_value = PollResult(
            state=PollingState.CAR_OFF,
            data={},
            any_success=False,
            voltage=12.0,
        )
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert coordinator.data is not None
    assert coordinator.data.get("FUEL_LEVEL") == 75.0


async def test_coordinator_scan_supported_pids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the scan_supported_standard_pids method."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on() as poller:
        poller.scan_supported_standard_pids.return_value = [
            "FUEL_LEVEL",
            "ENGINE_SPEED",
        ]
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        await mock_config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    result = await coordinator.async_scan_supported_standard_pids()
    assert result == ["FUEL_LEVEL", "ENGINE_SPEED"]


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
        await mock_config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    poller.is_connected = False
    poller.connect.return_value = False

    with pytest.raises(UpdateFailed):
        await coordinator.async_scan_supported_standard_pids()


async def test_coordinator_scan_adapter_out_of_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test scan_supported_standard_pids raises when adapter is not found."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        await mock_config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    with (
        patch(
            "homeassistant.components.elm327_obdii_ble.coordinator.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator.async_scan_supported_standard_pids()


async def test_coordinator_scan_runtime_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test scan_supported_standard_pids raises UpdateFailed on RuntimeError."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on() as poller:
        poller.scan_supported_standard_pids.side_effect = RuntimeError("disconnected")
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        await mock_config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    with pytest.raises(UpdateFailed):
        await coordinator.async_scan_supported_standard_pids()


async def test_coordinator_out_of_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator raises UpdateFailed when device is out of range."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        await mock_config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    with (
        patch(
            "homeassistant.components.elm327_obdii_ble.coordinator.async_address_present",
            return_value=False,
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()

    assert coordinator.update_interval == timedelta(seconds=OUT_OF_RANGE_POLL_SECONDS)


async def test_coordinator_poll_cycle_connect_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator raises UpdateFailed when connect fails during poll."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on() as poller:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        await mock_config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    poller.is_connected = False
    poller.connect.return_value = False

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
