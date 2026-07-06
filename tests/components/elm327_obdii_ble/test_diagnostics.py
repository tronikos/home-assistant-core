"""Tests for the diagnostics data provided by the elm327_obdii_ble integration."""

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import ELM327_SERVICE_INFO
from .conftest import mock_poller_car_on

from tests.components.bluetooth import inject_bluetooth_service_info
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

DOMAIN = "elm327_obdii_ble"


async def test_diagnostics(
    hass: HomeAssistant,
    mock_config_entry,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot(
        exclude=props("created_at", "modified_at", "entry_id", "time", "discovery_keys")
    )
