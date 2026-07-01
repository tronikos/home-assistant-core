"""Tests for the Universal OBD BLE config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.universal_obd_ble import config_flow
from homeassistant.components.universal_obd_ble.uops import CustomPid, UopsConfig
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.asyncio


async def test_user_step_no_devices(hass: HomeAssistant) -> None:
    """Test that the user step aborts when no devices are found."""
    flow = config_flow.UniversalObdConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.universal_obd_ble.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await flow.async_step_user()

    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_found"


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test that the user step shows a form when devices are discovered."""
    flow = config_flow.UniversalObdConfigFlow()
    flow.hass = hass

    mock_dev = MagicMock()
    mock_dev.address = "AA:BB:CC:DD:EE:FF"
    mock_dev.name = "Test Adapter"

    with patch(
        "homeassistant.components.universal_obd_ble.config_flow.async_discovered_service_info",
        return_value=[mock_dev],
    ):
        result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_vehicle_step_with_no_profile(hass: HomeAssistant) -> None:
    """Test that selecting 'none' produces an empty UopsConfig."""
    flow = config_flow.UniversalObdConfigFlow()
    flow.hass = hass
    flow._wican_profiles = {}

    with (
        patch(
            "homeassistant.components.universal_obd_ble.config_flow.list_builtin_profiles",
            return_value=[],
        ),
        patch(
            "homeassistant.components.universal_obd_ble.config_flow.fetch_wican_profiles",
            return_value={},
        ),
    ):
        result = await flow.async_step_vehicle({"profile": "none"})

    assert result["type"] == "form"
    assert result["step_id"] == "standard_pids"
    assert flow._profile_uops == UopsConfig()


async def test_standard_pids_step_creates_entry(hass: HomeAssistant) -> None:
    """Test that the standard PIDs step creates a config entry."""
    flow = config_flow.UniversalObdConfigFlow()
    flow.hass = hass
    flow._address = "AA:BB:CC:DD:EE:FF"
    flow._title = "Test"
    flow.atrv_supported = True
    flow._uuid_read = "0000fff1-0000-1000-8000-00805f9b34fb"
    flow._uuid_write = "0000fff2-0000-1000-8000-00805f9b34fb"
    flow._profile_uops = UopsConfig()

    result = flow._async_create_entry(
        UopsConfig(standard_pids=["ENGINE_SPEED"], custom_pids=[])
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Test"
    assert result["data"]["address"] == "AA:BB:CC:DD:EE:FF"
    assert "ENGINE_SPEED" in result["options"]["uops"]["standard_pids"]


async def test_options_flow_init_menu(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that the options flow shows the 3-item menu."""
    flow = config_flow.UniversalObdBleOptionsFlow(mock_config_entry)

    result = await flow.async_step_init()

    assert result["type"] == "menu"
    assert set(result["menu_options"]) == {"polling", "standard_pids", "custom_pids"}


async def test_options_flow_polling_saves(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that the polling options step saves correctly."""
    flow = config_flow.UniversalObdBleOptionsFlow(mock_config_entry)
    flow.hass = hass

    result = await flow.async_step_polling(
        {
            "voltage_check": "AT RV",
            "fast_poll": 10,
            "slow_poll": 600,
            "xs_poll": 7200,
            "voltage_on_threshold": 13.5,
            "voltage_off_threshold": 12.5,
            "voltage_grace_seconds": 60,
        }
    )

    assert result["type"] == "create_entry"
    assert result["data"]["fast_poll"] == 10
    assert result["data"]["slow_poll"] == 600


async def test_options_flow_custom_pid_add(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test adding a custom PID via the options flow."""
    flow = config_flow.UniversalObdBleOptionsFlow(mock_config_entry)
    flow.hass = hass

    result = await flow.async_step_custom_pid_edit(
        {
            "pid_name": "Test SOC",
            "mode": "22",
            "query": "028C1",
            "can_header": "7E5",
            "can_filter": "7ED",
            "init_extra": "",
            "formula": "B(4) / 2.55",
            "unit": "%",
            "device_class": "battery",
            "state_class": "measurement",
            "min_value": 0,
            "max_value": 100,
            "expected_bytes": 5,
            "remove": False,
        }
    )

    assert result["type"] == "create_entry"
    custom_pids = result["data"]["uops"]["custom_pids"]
    assert len(custom_pids) == 1
    assert custom_pids[0]["name"] == "Test SOC"
    assert custom_pids[0]["formula"] == "B(4) / 2.55"


async def test_options_flow_custom_pid_invalid_formula(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that an invalid formula shows an error."""
    flow = config_flow.UniversalObdBleOptionsFlow(mock_config_entry)
    flow.hass = hass

    result = await flow.async_step_custom_pid_edit(
        {
            "pid_name": "Bad",
            "mode": "22",
            "query": "028C1",
            "can_header": "",
            "can_filter": "",
            "init_extra": "",
            "formula": "__import__('os')",
            "unit": "",
            "device_class": "",
            "state_class": "",
            "min_value": None,
            "max_value": None,
            "expected_bytes": 0,
            "remove": False,
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "custom_pid_edit"
    assert result["errors"]["formula"] == "invalid_formula"


async def test_options_flow_custom_pid_invalid_hex(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test that invalid hex mode shows an error."""
    flow = config_flow.UniversalObdBleOptionsFlow(mock_config_entry)
    flow.hass = hass

    result = await flow.async_step_custom_pid_edit(
        {
            "pid_name": "Bad",
            "mode": "ZZ",
            "query": "028C1",
            "can_header": "",
            "can_filter": "",
            "init_extra": "",
            "formula": "B(0)",
            "unit": "",
            "device_class": "",
            "state_class": "",
            "min_value": None,
            "max_value": None,
            "expected_bytes": 0,
            "remove": False,
        }
    )

    assert result["type"] == "form"
    assert result["errors"]["mode"] == "invalid_hex"


async def test_options_flow_custom_pid_delete(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Test deleting a custom PID via the remove checkbox."""
    flow = config_flow.UniversalObdBleOptionsFlow(mock_config_entry)
    flow.hass = hass

    existing_pid = CustomPid(
        id="test-pid-id",
        name="Existing PID",
        mode="22",
        query="028C1",
        formula="B(0)",
    )
    flow._uops.custom_pids = [existing_pid]
    flow._editing_pid_id = "test-pid-id"

    result = await flow.async_step_custom_pid_edit({"remove": True})

    assert result["type"] == "create_entry"
    assert len(result["data"]["uops"]["custom_pids"]) == 0
