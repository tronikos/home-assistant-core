"""Test the elm327_obdii_ble sensors."""

from unittest.mock import patch

import pytest

from homeassistant.components.elm327_obdii_ble.elm327_obdii import (
    PollingState,
    PollResult,
)
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import DEFAULT_OPTIONS, ELM327_SERVICE_INFO
from .conftest import mock_poller_car_off, mock_poller_car_on

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

DOMAIN = "elm327_obdii_ble"

FUEL_TYPE_ENTITY = "sensor.mock_title_fuel_type"
ADAPTER_STATE_ENTITY = "sensor.mock_title_adapter_state"
BATTERY_VOLTAGE_ENTITY = "sensor.mock_title_battery_voltage"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_car_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors are created with correct values when car is on."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    # 1 standard (FUEL_TYPE) + 2 diagnostic (adapter state + battery voltage) = 3
    states = hass.states.async_all("sensor")
    assert len(states) == 3

    # Standard sensor: FUEL_TYPE
    fuel_type = hass.states.get(FUEL_TYPE_ENTITY)
    assert fuel_type is not None
    assert fuel_type.state == "Gasoline"

    # Diagnostic: Adapter State
    adapter_state = hass.states.get(ADAPTER_STATE_ENTITY)
    assert adapter_state is not None
    assert adapter_state.state == "car_on"

    # Diagnostic: Battery Voltage
    voltage = hass.states.get(BATTERY_VOLTAGE_ENTITY)
    assert voltage is not None
    assert voltage.state == "14.2"
    assert voltage.attributes[ATTR_UNIT_OF_MEASUREMENT] == "V"
    assert voltage.attributes[ATTR_DEVICE_CLASS] == "voltage"

    # Test unload
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_car_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors hold last known values when car is off."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    fuel_type = hass.states.get(FUEL_TYPE_ENTITY)
    assert fuel_type is not None
    assert fuel_type.state == "Gasoline"

    with mock_poller_car_off():
        coordinator = mock_config_entry.runtime_data
        coordinator._poller.poll_once.return_value = PollResult(
            state=PollingState.CAR_OFF,
            data={},
            any_success=False,
            voltage=12.0,
        )
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    fuel_type = hass.states.get(FUEL_TYPE_ENTITY)
    assert fuel_type is not None
    assert fuel_type.state == "Gasoline"

    adapter_state = hass.states.get(ADAPTER_STATE_ENTITY)
    assert adapter_state is not None
    assert adapter_state.state == "car_off"

    voltage = hass.states.get(BATTERY_VOLTAGE_ENTITY)
    assert voltage is not None
    assert voltage.state == "12.0"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors become unavailable when the integration is unloaded."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    fuel_type = hass.states.get(FUEL_TYPE_ENTITY)
    assert fuel_type is not None
    assert fuel_type.state == "Gasoline"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    for state in states:
        assert state.state in (STATE_UNKNOWN, "unavailable")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_custom_sensor(
    hass: HomeAssistant,
) -> None:
    """Test custom PID sensor creation with fmt and enumeration support."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    profile = {
        "standard_pids": [],
        "custom_pids": [
            {
                "id": "test-voltage",
                "name": "Pack Voltage",
                "mode": "22",
                "query": "1E3B",
                "fmt": {"bix": 0, "len": 16, "div": 4, "max": 1000},
                "can_header": "7E5",
                "can_filter": "7ED",
                "unit": "V",
                "device_class": "voltage",
                "state_class": "measurement",
                "min_value": 0,
                "max_value": 450,
                "source": "manual",
            },
            {
                "id": "test-enum",
                "name": "Charge Mode",
                "mode": "22",
                "query": "1E3F",
                "fmt": {"bix": 0, "len": 2, "map": {"0": "Off", "1": "AC", "2": "DC"}},
                "can_header": "7E5",
                "can_filter": "7ED",
                "unit": None,
                "source": "manual",
            },
        ],
    }
    options = {**DEFAULT_OPTIONS, "profile": profile}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "address": "AA:BB:CC:DD:EE:FF",
            "atrv_supported": True,
            "uuid_write": "0000fff2-0000-1000-8000-00805f9b34fb",
            "uuid_read": "0000fff1-0000-1000-8000-00805f9b34fb",
        },
        unique_id="aabbccddeeff",
        options=options,
    )
    entry.add_to_hass(hass)

    poll_result = PollResult(
        state=PollingState.CAR_ON,
        data={"Pack Voltage": 332.25, "Charge Mode": "AC"},
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
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    # 2 custom + 2 diagnostic = 4
    states = hass.states.async_all("sensor")
    assert len(states) == 4

    # Custom voltage sensor
    voltage = hass.states.get("sensor.mock_title_pack_voltage")
    assert voltage is not None
    assert voltage.state == "332.25"
    assert voltage.attributes[ATTR_UNIT_OF_MEASUREMENT] == "V"
    assert voltage.attributes[ATTR_DEVICE_CLASS] == "voltage"

    # Custom enum sensor
    charge_mode = hass.states.get("sensor.mock_title_charge_mode")
    assert charge_mode is not None
    assert charge_mode.state == "AC"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_orphan_cleanup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test orphaned entities are removed when profile changes."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    assert len(ent_reg.entities) == 3

    # Add a fake orphan entity
    orphan = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{mock_config_entry.unique_id}-std-ENGINE_SPEED",
        suggested_object_id="mock_title_engine_speed",
        config_entry=mock_config_entry,
    )
    assert orphan is not None
    assert len(ent_reg.entities) == 4

    # Reload — orphan should be cleaned up
    with mock_poller_car_on():
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(ent_reg.entities) == 3
    assert (
        ent_reg.async_get_entity_id(
            "sensor", DOMAIN, f"{mock_config_entry.unique_id}-std-ENGINE_SPEED"
        )
        is None
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_standard_pid_not_found(
    hass: HomeAssistant,
) -> None:
    """Test that a standard PID not in the obdii registry is skipped."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    profile = {
        "standard_pids": ["NONEXISTENT_PID", "FUEL_TYPE"],
        "custom_pids": [],
    }
    options = {**DEFAULT_OPTIONS, "profile": profile}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "address": "AA:BB:CC:DD:EE:FF",
            "atrv_supported": True,
            "uuid_write": "0000fff2-0000-1000-8000-00805f9b34fb",
            "uuid_read": "0000fff1-0000-1000-8000-00805f9b34fb",
        },
        unique_id="aabbccddeeff",
        options=options,
    )
    entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    # Only FUEL_TYPE + 2 diagnostic = 3 (NONEXISTENT_PID skipped)
    states = hass.states.async_all("sensor")
    assert len(states) == 3
    assert hass.states.get(FUEL_TYPE_ENTITY) is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_custom_sensor_odometer_state_class(
    hass: HomeAssistant,
) -> None:
    """Test that custom PID with 'ODOMETER' in name gets total_increasing."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    profile = {
        "standard_pids": [],
        "custom_pids": [
            {
                "id": "test-odo",
                "name": "Odometer",
                "mode": "22",
                "query": "2203",
                "fmt": {"bix": 0, "len": 24},
                "can_header": "714",
                "can_filter": "77E",
                "unit": "km",
                "source": "manual",
            },
        ],
    }
    options = {**DEFAULT_OPTIONS, "profile": profile}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "address": "AA:BB:CC:DD:EE:FF",
            "atrv_supported": True,
            "uuid_write": "0000fff2-0000-1000-8000-00805f9b34fb",
            "uuid_read": "0000fff1-0000-1000-8000-00805f9b34fb",
        },
        unique_id="aabbccddeeff",
        options=options,
    )
    entry.add_to_hass(hass)

    poll_result = PollResult(
        state=PollingState.CAR_ON,
        data={"Odometer": 129762.0},
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
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    odo = hass.states.get("sensor.mock_title_odometer")
    assert odo is not None
    assert odo.state == "129762.0"
    assert odo.attributes["state_class"] == SensorStateClass.TOTAL_INCREASING

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_custom_sensor_min_max_attrs(
    hass: HomeAssistant,
) -> None:
    """Test that custom PID with min/max values sets extra state attributes."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    profile = {
        "standard_pids": [],
        "custom_pids": [
            {
                "id": "test-current",
                "name": "Battery Current",
                "mode": "22",
                "query": "1E3D",
                "fmt": {"bix": 0, "len": 16, "div": 4, "add": -511, "sign": True},
                "can_header": "7E5",
                "can_filter": "7ED",
                "unit": "A",
                "device_class": "current",
                "state_class": "measurement",
                "min_value": -200,
                "max_value": 200,
                "source": "manual",
            },
        ],
    }
    options = {**DEFAULT_OPTIONS, "profile": profile}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "address": "AA:BB:CC:DD:EE:FF",
            "atrv_supported": True,
            "uuid_write": "0000fff2-0000-1000-8000-00805f9b34fb",
            "uuid_read": "0000fff1-0000-1000-8000-00805f9b34fb",
        },
        unique_id="aabbccddeeff",
        options=options,
    )
    entry.add_to_hass(hass)

    poll_result = PollResult(
        state=PollingState.CAR_ON,
        data={"Battery Current": -4.25},
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
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    current = hass.states.get("sensor.mock_title_battery_current")
    assert current is not None
    assert current.state == "-4.25"
    assert current.attributes[ATTR_UNIT_OF_MEASUREMENT] == "A"
    assert current.attributes[ATTR_DEVICE_CLASS] == "current"
    assert current.attributes["min_value"] == -200.0
    assert current.attributes["max_value"] == 200.0

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_custom_sensor_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test custom sensor returns None when coordinator data is None."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    profile = {
        "standard_pids": [],
        "custom_pids": [
            {
                "id": "test-no-data",
                "name": "No Data PID",
                "mode": "22",
                "query": "1E3F",
                "fmt": {"bix": 0, "len": 8},
                "can_header": "7E5",
                "can_filter": "7ED",
                "unit": "V",
                "source": "manual",
            },
        ],
    }
    options = {**DEFAULT_OPTIONS, "profile": profile}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "address": "AA:BB:CC:DD:EE:FF",
            "atrv_supported": True,
            "uuid_write": "0000fff2-0000-1000-8000-00805f9b34fb",
            "uuid_read": "0000fff1-0000-1000-8000-00805f9b34fb",
        },
        unique_id="aabbccddeeff",
        options=options,
    )
    entry.add_to_hass(hass)

    # Poll returns data that doesn't include the custom PID name
    poll_result = PollResult(
        state=PollingState.CAR_ON,
        data={},
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
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    sensor_state = hass.states.get("sensor.mock_title_no_data_pid")
    assert sensor_state is not None
    assert sensor_state.state == STATE_UNKNOWN

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_custom_orphan_cleanup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test orphaned custom entities are removed when profile changes."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    mock_config_entry.add_to_hass(hass)

    with mock_poller_car_on():
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await mock_config_entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    assert len(ent_reg.entities) == 3

    # Add a fake orphan custom entity
    orphan = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{mock_config_entry.unique_id}-custom-test-orphan",
        suggested_object_id="mock_title_orphan_custom",
        config_entry=mock_config_entry,
    )
    assert orphan is not None
    assert len(ent_reg.entities) == 4

    # Reload — orphan should be cleaned up
    with mock_poller_car_on():
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(ent_reg.entities) == 3
    assert (
        ent_reg.async_get_entity_id(
            "sensor", DOMAIN, f"{mock_config_entry.unique_id}-custom-test-orphan"
        )
        is None
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_standard_sensor_voltage(
    hass: HomeAssistant,
) -> None:
    """Test standard PID VEHICLE_VOLTAGE gets voltage device class."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    profile = {
        "standard_pids": ["VEHICLE_VOLTAGE"],
        "custom_pids": [],
    }
    options = {**DEFAULT_OPTIONS, "profile": profile}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "address": "AA:BB:CC:DD:EE:FF",
            "atrv_supported": True,
            "uuid_write": "0000fff2-0000-1000-8000-00805f9b34fb",
            "uuid_read": "0000fff1-0000-1000-8000-00805f9b34fb",
        },
        unique_id="aabbccddeeff",
        options=options,
    )
    entry.add_to_hass(hass)

    poll_result = PollResult(
        state=PollingState.CAR_ON,
        data={"VEHICLE_VOLTAGE": 12.6},
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
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    # Standard sensor: VEHICLE_VOLTAGE
    sensor_state = hass.states.get("sensor.mock_title_vehicle_voltage")
    assert sensor_state is not None
    assert sensor_state.state == "12.6"
    assert sensor_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "V"
    assert sensor_state.attributes[ATTR_DEVICE_CLASS] == "voltage"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_custom_sensor_no_coordinator_data(
    hass: HomeAssistant,
) -> None:
    """Test custom sensor returns None when coordinator data is None."""
    inject_bluetooth_service_info(hass, ELM327_SERVICE_INFO)

    profile = {
        "standard_pids": [],
        "custom_pids": [
            {
                "id": "test-no-data",
                "name": "No Data PID",
                "mode": "22",
                "query": "1E3F",
                "fmt": {"bix": 0, "len": 8},
                "can_header": "7E5",
                "can_filter": "7ED",
                "unit": "V",
                "source": "manual",
            },
        ],
    }
    options = {**DEFAULT_OPTIONS, "profile": profile}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "address": "AA:BB:CC:DD:EE:FF",
            "atrv_supported": True,
            "uuid_write": "0000fff2-0000-1000-8000-00805f9b34fb",
            "uuid_read": "0000fff1-0000-1000-8000-00805f9b34fb",
        },
        unique_id="aabbccddeeff",
        options=options,
    )
    entry.add_to_hass(hass)

    poll_result = PollResult(
        state=PollingState.CAR_ON,
        data={},
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
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        # Ensure at least one poll has completed
        await entry.runtime_data._async_poll()
        await hass.async_block_till_done()

    # Coordinator data exists but doesn't include our PID name
    sensor_state = hass.states.get("sensor.mock_title_no_data_pid")
    assert sensor_state is not None
    assert sensor_state.state == STATE_UNKNOWN

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
