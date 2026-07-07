"""Tests for the elm327_obdii_ble integration."""

from unittest.mock import patch

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

DOMAIN = "elm327_obdii_ble"

ELM327_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="OBDII",
    manufacturer_data={},
    service_data={},
    service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="OBDII",
        service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "OBDII"),
    time=0,
    connectable=True,
    tx_power=-127,
)

USER_INPUT = {
    CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
}

DEFAULT_PROFILE = {
    "standard_pids": ["FUEL_LEVEL"],
    "custom_pids": [],
}

DEFAULT_OPTIONS = {
    "profile": DEFAULT_PROFILE,
    "voltage_check": True,
    "voltage_on_threshold": 13.1,
    "voltage_off_threshold": 12.8,
    "voltage_grace_seconds": 30,
}


def patch_async_setup_entry(return_value=True):
    """Patch async setup entry to return True."""
    return patch(
        "homeassistant.components.elm327_obdii_ble.async_setup_entry",
        return_value=return_value,
    )
