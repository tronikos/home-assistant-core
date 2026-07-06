"""Define fixtures available for all tests."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from bleak.exc import BleakError
import pytest

from homeassistant.components.elm327_obdii_ble.elm327_obdii import (
    ConnectionTestResult,
    PollingState,
    PollResult,
)
from homeassistant.const import CONF_ADDRESS

from . import DEFAULT_OPTIONS, DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
            "atrv_supported": True,
            "uuid_write": "0000fff2-0000-1000-8000-00805f9b34fb",
            "uuid_read": "0000fff1-0000-1000-8000-00805f9b34fb",
        },
        unique_id="aa:bb:cc:dd:ee:ff",
        options=DEFAULT_OPTIONS,
    )


@contextmanager
def mock_poller_car_on():
    """Mock the Poller to simulate a car-on state with data.

    The Poller.connect returns True, poll_once returns a PollResult with
    CAR_ON state, 14.2V voltage, and a FUEL_TYPE value of "Gasoline".
    """
    poll_result = PollResult(
        state=PollingState.CAR_ON,
        data={"FUEL_TYPE": "Gasoline"},
        any_success=True,
        voltage=14.2,
    )

    with patch(
        "homeassistant.components.elm327_obdii_ble.coordinator.Poller"
    ) as mock_poller_cls:
        poller = mock_poller_cls.return_value
        poller.connect.return_value = True
        poller.is_connected = True
        poller.poll_once.return_value = poll_result
        poller.disconnect.return_value = None
        yield poller


@contextmanager
def mock_poller_car_off():
    """Mock the Poller to simulate a car-off state.

    The Poller.connect returns True, poll_once returns a PollResult with
    CAR_OFF state, 12.0V voltage, and no data.
    """
    poll_result = PollResult(
        state=PollingState.CAR_OFF,
        data={},
        any_success=False,
        voltage=12.0,
    )

    with patch(
        "homeassistant.components.elm327_obdii_ble.coordinator.Poller"
    ) as mock_poller_cls:
        poller = mock_poller_cls.return_value
        poller.connect.return_value = True
        poller.is_connected = True
        poller.poll_once.return_value = poll_result
        poller.disconnect.return_value = None
        yield poller


@contextmanager
def mock_poller_transport_error():
    """Mock the Poller to simulate a transport error on poll."""
    with patch(
        "homeassistant.components.elm327_obdii_ble.coordinator.Poller"
    ) as mock_poller_cls:
        poller = mock_poller_cls.return_value
        poller.connect.return_value = True
        poller.is_connected = True
        poller.poll_once.side_effect = BleakError("disconnected")
        poller.disconnect.return_value = None
        yield poller


@pytest.fixture
def mock_probe_adapter_success():
    """Mock probe_adapter to return a successful connection test."""
    result = ConnectionTestResult(
        success=True,
        uuid_write="0000fff2-0000-1000-8000-00805f9b34fb",
        uuid_read="0000fff1-0000-1000-8000-00805f9b34fb",
        scanned_supported=["FUEL_TYPE"],
    )
    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.probe_adapter",
        return_value=result,
    ):
        yield result


@pytest.fixture
def mock_probe_adapter_failure():
    """Mock probe_adapter to return a failed connection test."""
    result = ConnectionTestResult(
        success=None,
        uuid_write="0000fff2-0000-1000-8000-00805f9b34fb",
        uuid_read="0000fff1-0000-1000-8000-00805f9b34fb",
        scanned_supported=None,
    )
    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.probe_adapter",
        return_value=result,
    ):
        yield result


@pytest.fixture
def mock_fetch_wican_profiles():
    """Mock fetch_wican_profiles to return a test profile."""
    wican_profiles = {
        "Test: Generic": {
            "car_model": "Test: Generic",
            "init": "",
            "pids": [
                {
                    "pid": "22028C1",
                    "pid_init": "ATSH7E5;ATCRA7ED;",
                    "parameters": [
                        {
                            "name": "SOC BMS",
                            "expression": "B4/2.5",
                            "unit": "%",
                            "class": "battery",
                        }
                    ],
                }
            ],
        }
    }
    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.fetch_wican_profiles",
        new_callable=AsyncMock,
        return_value=wican_profiles,
    ):
        yield wican_profiles


@pytest.fixture
def mock_fetch_obdb_matrix():
    """Mock fetch_obdb_matrix to return test signals."""
    obdb_vehicles = {
        ("Volkswagen", "e-Golf"): [
            {
                "bitLength": 16,
                "bitOffset": 0,
                "cmd": {"22": "1E3B"},
                "fmt": {"div": 4, "len": 16, "max": 1000, "unit": "volts"},
                "hdr": "7E5",
                "id": "EGOLF_HVBAT_VOLTS",
                "make": "Volkswagen",
                "model": "e-Golf",
                "name": "HV battery voltage",
                "path": "Battery",
                "pid": "22",
                "unit": "volts",
            }
        ]
    }
    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.fetch_obdb_matrix",
        new_callable=AsyncMock,
        return_value=obdb_vehicles,
    ):
        yield obdb_vehicles


@pytest.fixture
def mock_fetch_obdb_repo_default():
    """Mock fetch_obdb_repo_default_json to return test repo data."""
    repo_default = {
        "commands": [
            {
                "hdr": "7E5",
                "rax": "7ED",
                "cmd": {"22": "1E3B"},
                "signals": [
                    {
                        "id": "EGOLF_HVBAT_VOLTS",
                        "fmt": {"div": 4, "len": 16, "max": 1000, "unit": "volts"},
                        "name": "HV battery voltage",
                    }
                ],
            }
        ]
    }
    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.fetch_obdb_repo_default_json",
        new_callable=AsyncMock,
        return_value=repo_default,
    ):
        yield repo_default
