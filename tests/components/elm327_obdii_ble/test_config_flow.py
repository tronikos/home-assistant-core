"""Test the elm327_obdii_ble config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.elm327_obdii_ble.config_flow import (
    _ACTION_ADD,
    _ACTION_BACK,
)
from homeassistant.components.elm327_obdii_ble.const import (
    CONF_ATRV_SUPPORTED,
    CONF_GRACE_PERIOD,
    CONF_PROFILE,
    CONF_UUID_READ,
    CONF_UUID_WRITE,
    CONF_VOLTAGE_CHECK,
    CONF_VOLTAGE_OFF,
    CONF_VOLTAGE_ON,
)
from homeassistant.components.elm327_obdii_ble.elm327_obdii import (
    ConnectionTestResult,
    FmtValidationError,
    ProfileConfig,
)
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import ELM327_SERVICE_INFO, USER_INPUT, patch_async_setup_entry

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

DOMAIN = "elm327_obdii_ble"


def create_mock_entry(hass: HomeAssistant, options=None) -> MockConfigEntry:
    """Create a mock config entry with default options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_ATRV_SUPPORTED: True,
            CONF_UUID_READ: "read-uuid",
            CONF_UUID_WRITE: "write-uuid",
        },
        options=options
        or {
            CONF_PROFILE: ProfileConfig().to_dict(),
            CONF_VOLTAGE_CHECK: True,
            CONF_VOLTAGE_ON: 13.1,
            CONF_VOLTAGE_OFF: 12.2,
            CONF_GRACE_PERIOD: 30,
        },
    )
    entry.add_to_hass(hass)
    return entry


async def test_bluetooth_discovery(
    hass: HomeAssistant,
    mock_probe_adapter_success,
) -> None:
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=ELM327_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "vehicle"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile": "none"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "standard_pids"

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"standard_pids": ["FUEL_TYPE"]},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OBDII (EEFF)"
    assert result["data"][CONF_ADDRESS] == "AA:BB:CC:DD:EE:FF"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_discovery_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that duplicate entries are aborted."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=ELM327_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_setup_none(
    hass: HomeAssistant,
    mock_probe_adapter_success,
) -> None:
    """Test manual user setup with no profile (standard PIDs only)."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "vehicle"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile": "none"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "standard_pids"

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"standard_pids": ["FUEL_TYPE"]},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESS] == "AA:BB:CC:DD:EE:FF"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_setup_wican(
    hass: HomeAssistant,
    mock_probe_adapter_success,
    mock_fetch_wican_profiles,
) -> None:
    """Test manual user setup importing a WiCAN profile."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["step_id"] == "vehicle"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile": "__import_wican__"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "wican"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile": "Test: Generic"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "standard_pids"

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"standard_pids": ["FUEL_TYPE"]},
        )
    await hass.async_block_till_done()

    assert result["step_id"] == "custom_pids_select"

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"custom_pids": ["22:028C1:SOC BMS"]},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_setup_wican_unknown_profile(
    hass: HomeAssistant,
    mock_probe_adapter_success,
    mock_fetch_wican_profiles,
) -> None:
    """Test manual user setup selecting a non-existent WiCAN profile choice."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["step_id"] == "vehicle"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile": "__import_wican__"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "wican"

    # Access the handler directly to bypass selector validation
    flow_handler = hass.config_entries.flow._progress[result["flow_id"]]
    result = await flow_handler.async_step_wican(
        {"profile": "some_completely_unknown_profile_name"}
    )
    flow_handler.cur_step = result
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "standard_pids"

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"standard_pids": ["FUEL_TYPE"]},
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_setup_obdb(
    hass: HomeAssistant,
    mock_probe_adapter_success,
    mock_fetch_obdb_matrix,
    mock_fetch_obdb_repo_default,
) -> None:
    """Test manual user setup importing an OBDb profile."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["step_id"] == "vehicle"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile": "__import_obdb__"},
    )
    assert result["step_id"] == "obdb_make"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"make": "Volkswagen"},
    )
    assert result["step_id"] == "obdb_model"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"model": "e-Golf"},
    )
    assert result["step_id"] == "obdb_year"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"year": "all"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "standard_pids"

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"standard_pids": ["FUEL_TYPE"]},
        )
    await hass.async_block_till_done()

    assert result["step_id"] == "custom_pids_select"

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"custom_pids": ["EGOLF_HVBAT_VOLTS"]},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_obdb_fetch_fails(
    hass: HomeAssistant,
    mock_probe_adapter_success,
) -> None:
    """Test OBDb fetch failure returns to vehicle step with error."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["step_id"] == "vehicle"

    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.fetch_obdb_matrix",
        new_callable=AsyncMock,
        return_value={},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"profile": "__import_obdb__"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "vehicle"
    errors = result["errors"]
    assert errors is not None
    assert errors["base"] == "obdb_fetch_failed"

    # Flow can recover — user picks None instead
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile": "none"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "standard_pids"

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"standard_pids": ["FUEL_TYPE"]},
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_wican_fetch_fails(
    hass: HomeAssistant,
    mock_probe_adapter_success,
) -> None:
    """Test WiCAN fetch failure returns to vehicle step with error."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["step_id"] == "vehicle"

    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.fetch_wican_profiles",
        new_callable=AsyncMock,
        return_value={},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"profile": "__import_wican__"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "vehicle"
    errors = result["errors"]
    assert errors is not None
    assert errors["base"] == "wican_fetch_failed"

    # Flow can recover — user picks None instead
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile": "none"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "standard_pids"

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"standard_pids": ["FUEL_TYPE"]},
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_connection_step_success(
    hass: HomeAssistant,
    mock_probe_adapter_failure,
) -> None:
    """Test manual connection step with successful setup afterwards."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_char = MagicMock()
    mock_char.uuid = "0000fff1-0000-1000-8000-00805f9b34fb"
    mock_char.description = "Mock Characteristic"

    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.async_get_characteristics",
        return_value=[mock_char],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"

    # Simulate probe_adapter returning a successful result
    mock_success_result = ConnectionTestResult(
        success=True,
        uuid_write="0000fff1-0000-1000-8000-00805f9b34fb",
        uuid_read="0000fff1-0000-1000-8000-00805f9b34fb",
        scanned_supported=["FUEL_TYPE"],
    )

    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.probe_adapter",
        return_value=mock_success_result,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_UUID_READ: "0000fff1-0000-1000-8000-00805f9b34fb",
                CONF_UUID_WRITE: "0000fff1-0000-1000-8000-00805f9b34fb",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "vehicle"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile": "none"},
    )
    assert result["step_id"] == "standard_pids"
    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"standard_pids": ["FUEL_TYPE"]},
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_connection_test_fails(
    hass: HomeAssistant,
    mock_probe_adapter_failure,
) -> None:
    """Test connection test failure shows connection step with no initial error."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_char = MagicMock()
    mock_char.uuid = "0000fff1-0000-1000-8000-00805f9b34fb"
    mock_char.description = "Mock Characteristic"

    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.async_get_characteristics",
        return_value=[mock_char],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"
    # No error is shown immediately; the user is just prompted to select characteristics manually.
    assert result["errors"] is None

    # Proceed to finish the flow
    mock_success_result = ConnectionTestResult(
        success=True,
        uuid_write="0000fff1-0000-1000-8000-00805f9b34fb",
        uuid_read="0000fff1-0000-1000-8000-00805f9b34fb",
        scanned_supported=["FUEL_TYPE"],
    )
    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.probe_adapter",
        return_value=mock_success_result,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_UUID_READ: "0000fff1-0000-1000-8000-00805f9b34fb",
                CONF_UUID_WRITE: "0000fff1-0000-1000-8000-00805f9b34fb",
            },
        )
    assert result["step_id"] == "vehicle"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile": "none"},
    )
    assert result["step_id"] == "standard_pids"
    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"standard_pids": ["FUEL_TYPE"]},
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_setup_device_not_found(
    hass: HomeAssistant,
    mock_probe_adapter_success,
) -> None:
    """Test manual user setup errors with device_not_found when the specified device is not in cache."""
    # Inject a valid device so the scan doesn't abort with no_devices_found
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            "address": "AA:BB:CC:DD:EE:00"
        },  # A different address not in the BLE cache
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "device_not_found"}

    # Complete the flow by picking a valid address
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"},
    )
    assert result["step_id"] == "vehicle"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile": "none"},
    )
    assert result["step_id"] == "standard_pids"
    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"standard_pids": ["FUEL_TYPE"]},
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_setup_no_devices_found(hass: HomeAssistant) -> None:
    """Test manual user setup aborts with no_devices_found when no BLE devices are present."""
    # We deliberately DO NOT inject any BLE devices here

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={"address": "AA:BB:CC:DD:EE:00"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_connection_no_characteristics(
    hass: HomeAssistant,
    mock_probe_adapter_failure,
) -> None:
    """Test that discovery aborts when no characteristics are found."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.async_get_characteristics",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_characteristics_found"


async def test_bluetooth_discovery_connection_test_fails(
    hass: HomeAssistant,
    mock_probe_adapter_failure,
) -> None:
    """Test bluetooth discovery when connection test fails."""
    mock_char = MagicMock()
    mock_char.uuid = "0000fff1-0000-1000-8000-00805f9b34fb"
    mock_char.description = "Mock Characteristic"

    with (
        patch(
            "homeassistant.components.elm327_obdii_ble.config_flow.async_get_characteristics",
            return_value=[mock_char],
        ),
        patch(
            "homeassistant.components.elm327_obdii_ble.config_flow.async_ble_device_from_address",
            return_value=ELM327_SERVICE_INFO.device,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=ELM327_SERVICE_INFO,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with (
        patch(
            "homeassistant.components.elm327_obdii_ble.config_flow.async_get_characteristics",
            return_value=[mock_char],
        ),
        patch(
            "homeassistant.components.elm327_obdii_ble.config_flow.async_ble_device_from_address",
            return_value=ELM327_SERVICE_INFO.device,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"

    mock_success_result = ConnectionTestResult(
        success=True,
        uuid_write="0000fff1-0000-1000-8000-00805f9b34fb",
        uuid_read="0000fff1-0000-1000-8000-00805f9b34fb",
        scanned_supported=["FUEL_TYPE"],
    )
    with (
        patch(
            "homeassistant.components.elm327_obdii_ble.config_flow.probe_adapter",
            return_value=mock_success_result,
        ),
        patch(
            "homeassistant.components.elm327_obdii_ble.config_flow.async_ble_device_from_address",
            return_value=ELM327_SERVICE_INFO.device,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_UUID_READ: "0000fff1-0000-1000-8000-00805f9b34fb",
                CONF_UUID_WRITE: "0000fff1-0000-1000-8000-00805f9b34fb",
            },
        )
    assert result["step_id"] == "vehicle"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile": "none"},
    )
    assert result["step_id"] == "standard_pids"
    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"standard_pids": ["FUEL_TYPE"]},
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_setup_init_form(
    hass: HomeAssistant,
    mock_probe_adapter_success,
) -> None:
    """Test user setup step when no initial data is provided."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=None,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"},
    )
    assert result["step_id"] == "vehicle"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile": "none"},
    )
    assert result["step_id"] == "standard_pids"
    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"standard_pids": ["FUEL_TYPE"]},
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_connection_device_not_found(
    hass: HomeAssistant,
    mock_probe_adapter_failure,
) -> None:
    """Test that the connection step aborts if the BLE device disappears."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_char = MagicMock()
    mock_char.uuid = "0000fff1-0000-1000-8000-00805f9b34fb"
    mock_char.description = "Mock Characteristic"

    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.async_get_characteristics",
        return_value=[mock_char],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"

    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.async_ble_device_from_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_UUID_READ: "0000fff1-0000-1000-8000-00805f9b34fb",
                CONF_UUID_WRITE: "0000fff1-0000-1000-8000-00805f9b34fb",
            },
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_not_found"


async def test_user_setup_unknown_profile(
    hass: HomeAssistant,
    mock_probe_adapter_success,
) -> None:
    """Test when an unknown profile choice is submitted in the vehicle step."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["step_id"] == "vehicle"

    # Access the handler directly to bypass selector validation and test fallback code paths
    flow_handler = hass.config_entries.flow._progress[result["flow_id"]]
    result = await flow_handler.async_step_vehicle(
        {"profile": "some_completely_unknown_profile_value"}
    )
    flow_handler.cur_step = result
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "standard_pids"

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"standard_pids": ["FUEL_TYPE"]},
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_setup_obdb_year_variations(
    hass: HomeAssistant,
    mock_probe_adapter_success,
    mock_fetch_obdb_matrix,
    mock_fetch_obdb_repo_default,
) -> None:
    """Test OBDb year selection with multiple year ranges and specific year selection."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    # Clear and update the mutable mock matrix dictionary provided by the fixture
    mock_fetch_obdb_matrix.clear()
    mock_fetch_obdb_matrix.update(
        {
            ("Volkswagen", "e-Golf"): [
                {"name": "Signal 1", "modelYears": [2018]},
                {"name": "Signal 2", "modelYears": [2019, 2021]},
                {"name": "Signal 3", "modelYears": []},
                {"name": "Signal 4", "modelYears": None},
            ]
        }
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["step_id"] == "vehicle"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile": "__import_obdb__"},
    )
    assert result["step_id"] == "obdb_make"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"make": "Volkswagen"},
    )
    assert result["step_id"] == "obdb_model"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"model": "e-Golf"},
    )
    assert result["step_id"] == "obdb_year"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"year": "2020"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "standard_pids"

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"standard_pids": ["FUEL_TYPE"]},
        )
    await hass.async_block_till_done()

    # Since the mock database profile has no valid parseable custom PIDs,
    # the flow skips custom PID selection and directly creates the entry.
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_standard_pids_scanned_none(
    hass: HomeAssistant,
) -> None:
    """Test standard PIDs step when no scanned supported list is available."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_result = ConnectionTestResult(
        success=True,
        uuid_write="write-uuid",
        uuid_read="read-uuid",
        scanned_supported=None,
    )

    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.probe_adapter",
        return_value=mock_result,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=USER_INPUT,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "vehicle"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile": "none"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "standard_pids"
    assert "Could not scan the ECU" in result["description_placeholders"]["warning"]

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"standard_pids": ["FUEL_TYPE"]},
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_battery(hass: HomeAssistant) -> None:
    """Test options flow battery guard step."""
    entry = create_mock_entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "battery"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "battery"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_VOLTAGE_CHECK: False,
            CONF_VOLTAGE_ON: 12.8,
            CONF_VOLTAGE_OFF: 11.5,
            CONF_GRACE_PERIOD: 60,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_VOLTAGE_CHECK] is False
    assert entry.options[CONF_VOLTAGE_ON] == 12.8
    assert entry.options[CONF_VOLTAGE_OFF] == 11.5
    assert entry.options[CONF_GRACE_PERIOD] == 60


async def test_options_flow_standard_pids_success(hass: HomeAssistant) -> None:
    """Test options flow standard PIDs step with successful ECU scan."""
    entry = create_mock_entry(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.async_scan_supported_standard_pids = AsyncMock(
        return_value=["FUEL_TYPE"]
    )
    entry.runtime_data = mock_coordinator

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "standard_pids"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "standard_pids"
    assert result["description_placeholders"]["warning"] == ""

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"standard_pids": ["FUEL_TYPE"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    profile = ProfileConfig.from_dict(entry.options[CONF_PROFILE])
    assert profile.standard_pids == ["FUEL_TYPE"]


async def test_options_flow_standard_pids_scan_fails(hass: HomeAssistant) -> None:
    """Test options flow standard PIDs step when ECU scan fails."""
    entry = create_mock_entry(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.async_scan_supported_standard_pids = AsyncMock(
        side_effect=UpdateFailed("Connection lost")
    )
    entry.runtime_data = mock_coordinator

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "standard_pids"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "standard_pids"
    assert "Could not scan the ECU" in result["description_placeholders"]["warning"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"standard_pids": []},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_standard_pids_no_coordinator(hass: HomeAssistant) -> None:
    """Test options flow standard PIDs step when coordinator is missing."""
    entry = create_mock_entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "standard_pids"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "standard_pids"
    assert "Could not scan the ECU" in result["description_placeholders"]["warning"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"standard_pids": []},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_custom_pids_back(hass: HomeAssistant) -> None:
    """Test options flow custom PIDs menu back button."""
    entry = create_mock_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "custom_pids"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom_pids"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"action": _ACTION_BACK},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "battery"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_VOLTAGE_CHECK: True,
            CONF_VOLTAGE_ON: 13.1,
            CONF_VOLTAGE_OFF: 12.2,
            CONF_GRACE_PERIOD: 30,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_custom_pid_add_validation_failures(
    hass: HomeAssistant,
) -> None:
    """Test validation errors when adding/editing custom PIDs."""
    entry = create_mock_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "custom_pids"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"action": _ACTION_ADD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom_pid_edit"

    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.form_input_to_fmt_from_hybrid",
        return_value=None,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "pid_name": "Test PID",
                "mode": "G1",
                "query": "ZZ",
                "can_header": "invalid_header",
                "can_filter": "invalid_filter",
                "init_extra": "AT SP 6",
                "formula": "invalid_formula_xyz",
                "bix": 0,
                "len": 1,
                "mul": None,
                "div": None,
                "add": None,
                "sign": False,
                "blsb": False,
                "min": None,
                "max": None,
                "map_text": "",
                "unit": "V",
                "device_class": "",
                "state_class": "",
                "min_value": None,
                "max_value": None,
                "expected_bytes": 0,
                "remove": False,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom_pid_edit"
    assert "mode" in result["errors"]
    assert "query" in result["errors"]
    assert "can_header" in result["errors"]
    assert "can_filter" in result["errors"]
    assert "formula" in result["errors"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "pid_name": "Test PID Corrected",
            "mode": "22",
            "query": "01",
            "can_header": "",
            "can_filter": "",
            "init_extra": "",
            "formula": "A",
            "bix": 0,
            "len": 1,
            "mul": None,
            "div": None,
            "add": None,
            "sign": False,
            "blsb": False,
            "min": None,
            "max": None,
            "map_text": "",
            "unit": "V",
            "device_class": "",
            "state_class": "",
            "min_value": None,
            "max_value": None,
            "expected_bytes": 0,
            "remove": False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_custom_pid_add_fmt_validation_error(
    hass: HomeAssistant,
) -> None:
    """Test validation errors when validate_fmt raises FmtValidationError."""
    entry = create_mock_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "custom_pids"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"action": _ACTION_ADD},
    )

    with patch(
        "homeassistant.components.elm327_obdii_ble.config_flow.validate_fmt",
        side_effect=FmtValidationError("Fmt check failed"),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "pid_name": "Test PID",
                "mode": "22",
                "query": "01",
                "can_header": "",
                "can_filter": "",
                "init_extra": "",
                "formula": "A",
                "bix": 0,
                "len": 1,
                "mul": None,
                "div": None,
                "add": None,
                "sign": False,
                "blsb": False,
                "min": None,
                "max": None,
                "map_text": "",
                "unit": "V",
                "device_class": "",
                "state_class": "",
                "min_value": None,
                "max_value": None,
                "expected_bytes": 0,
                "remove": False,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert "formula" in result["errors"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "pid_name": "Test PID Corrected",
            "mode": "22",
            "query": "01",
            "can_header": "",
            "can_filter": "",
            "init_extra": "",
            "formula": "A",
            "bix": 0,
            "len": 1,
            "mul": None,
            "div": None,
            "add": None,
            "sign": False,
            "blsb": False,
            "min": None,
            "max": None,
            "map_text": "",
            "unit": "V",
            "device_class": "",
            "state_class": "",
            "min_value": None,
            "max_value": None,
            "expected_bytes": 0,
            "remove": False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_custom_pid_lifecycle(hass: HomeAssistant) -> None:
    """Test the complete lifecycle of custom PIDs (add, edit, remove)."""
    entry = create_mock_entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "custom_pids"},
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"action": _ACTION_ADD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom_pid_edit"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "pid_name": "Battery SOC",
            "mode": "22",
            "query": "028C",
            "can_header": "7E4",
            "can_filter": "7EC",
            "init_extra": "AT SH 7E4",
            "formula": "A * 0.5",
            "bix": 0,
            "len": 1,
            "mul": None,
            "div": None,
            "add": None,
            "sign": False,
            "blsb": False,
            "min": None,
            "max": None,
            "map_text": "",
            "unit": "%",
            "device_class": "battery",
            "state_class": "measurement",
            "min_value": 0.0,
            "max_value": 100.0,
            "expected_bytes": 1,
            "remove": False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    profile = ProfileConfig.from_dict(entry.options[CONF_PROFILE])
    assert len(profile.custom_pids) == 1
    pid = profile.custom_pids[0]
    assert pid.name == "Battery SOC"
    assert pid.mode == "22"
    assert pid.query == "028C"
    assert pid.can_header == "7E4"
    assert pid.can_filter == "7EC"
    assert pid.unit == "%"
    assert pid.device_class == "battery"
    assert pid.state_class == "measurement"
    assert pid.min_value == 0.0
    assert pid.max_value == 100.0
    assert pid.expected_bytes == 1

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "custom_pids"},
    )

    pid_id = pid.id
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"action": pid_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom_pid_edit"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "pid_name": "Battery SOC Edited",
            "mode": "22",
            "query": "028C",
            "can_header": "7E4",
            "can_filter": "7EC",
            "init_extra": "AT SH 7E4",
            "formula": "A * 0.5",
            "bix": 0,
            "len": 1,
            "mul": None,
            "div": None,
            "add": None,
            "sign": False,
            "blsb": False,
            "min": None,
            "max": None,
            "map_text": "",
            "unit": "%",
            "device_class": "battery",
            "state_class": "measurement",
            "min_value": 10.0,
            "max_value": 90.0,
            "expected_bytes": 1,
            "remove": False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    profile = ProfileConfig.from_dict(entry.options[CONF_PROFILE])
    assert len(profile.custom_pids) == 1
    pid = profile.custom_pids[0]
    assert pid.name == "Battery SOC Edited"
    assert pid.min_value == 10.0
    assert pid.max_value == 90.0

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "custom_pids"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"action": pid_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom_pid_edit"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "pid_name": "Battery SOC Edited",
            "mode": "22",
            "query": "028C",
            "can_header": "7E4",
            "can_filter": "7EC",
            "init_extra": "AT SH 7E4",
            "formula": "A * 0.5",
            "bix": 0,
            "len": 1,
            "mul": None,
            "div": None,
            "add": None,
            "sign": False,
            "blsb": False,
            "min": None,
            "max": None,
            "map_text": "",
            "unit": "%",
            "device_class": "battery",
            "state_class": "measurement",
            "min_value": 10.0,
            "max_value": 90.0,
            "expected_bytes": 1,
            "remove": True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    profile = ProfileConfig.from_dict(entry.options[CONF_PROFILE])
    assert len(profile.custom_pids) == 0


async def test_options_flow_custom_pid_remove_non_existent(hass: HomeAssistant) -> None:
    """Test options flow custom PID edit step when removing a non-existent custom PID."""
    entry = create_mock_entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "custom_pids"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"action": _ACTION_ADD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom_pid_edit"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "pid_name": "Nonexistent",
            "mode": "22",
            "query": "028C",
            "can_header": "",
            "can_filter": "",
            "init_extra": "",
            "formula": "A",
            "bix": 0,
            "len": 1,
            "mul": None,
            "div": None,
            "add": None,
            "sign": False,
            "blsb": False,
            "min": None,
            "max": None,
            "map_text": "",
            "unit": "",
            "device_class": "",
            "state_class": "",
            "min_value": None,
            "max_value": None,
            "expected_bytes": 0,
            "remove": True,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom_pids"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"action": _ACTION_BACK},
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "battery"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_VOLTAGE_CHECK: True,
            CONF_VOLTAGE_ON: 13.1,
            CONF_VOLTAGE_OFF: 12.2,
            CONF_GRACE_PERIOD: 30,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_custom_pid_edit_invalid_id(hass: HomeAssistant) -> None:
    """Test options flow custom PID edit step with an invalid editing ID."""
    entry = create_mock_entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "custom_pids"},
    )

    flow_handler = hass.config_entries.options._progress[result["flow_id"]]
    result = await flow_handler.async_step_custom_pids(
        {"action": "some_random_non_existent_id"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom_pids"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"action": _ACTION_BACK},
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "battery"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_VOLTAGE_CHECK: True,
            CONF_VOLTAGE_ON: 13.1,
            CONF_VOLTAGE_OFF: 12.2,
            CONF_GRACE_PERIOD: 30,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
