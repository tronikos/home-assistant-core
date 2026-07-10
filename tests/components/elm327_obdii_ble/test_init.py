"""Test the elm327_obdii_ble init."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import ELM327_SERVICE_INFO
from .conftest import mock_poller_car_on, mock_poller_transport_error

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

DOMAIN = "elm327_obdii_ble"


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup of a config entry."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_device_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup succeeds even when BLE device is not found yet.

    The coordinator handles the out-of-range state internally — it will
    start polling as soon as the first advertisement arrives.
    """
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        mock_poller_car_on(),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading a config entry."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED  # type: ignore[comparison-overlap]


async def test_setup_entry_transport_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup succeeds even if the first poll hits a transport error.

    The coordinator should still reach LOADED state — the transport error
    is caught by poll_once and surfaces as UpdateFailed, not setup failure.
    """
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_transport_error():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_options_update_triggers_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that updating options triggers a config entry reload."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Update options — should trigger reload via the listener
    new_options = {**mock_config_entry.options, "voltage_on_threshold": 13.5}
    hass.config_entries.async_update_entry(mock_config_entry, options=new_options)
    await hass.async_block_till_done()

    # Entry should still be loaded after reload
    assert mock_config_entry.state is ConfigEntryState.LOADED
