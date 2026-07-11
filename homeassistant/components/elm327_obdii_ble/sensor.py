"""Sensor platform for the ELM327 OBD-II BLE integration."""

import logging
from typing import TYPE_CHECKING, Any, Final, override

from elm327_obdii import (
    CustomPid,
    PollingState,
    ProfileConfig,
    format_sensor_value,
    get_list_of_units,
    get_standard_command,
    propose_device_class,
    propose_icon,
    propose_state_class,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify

from .const import CONF_PROFILE
from .coordinator import Elm327ObdiiCoordinator
from .entity import Elm327ObdiiEntity

if TYPE_CHECKING:
    from . import Elm327ObdiiConfigEntry

PARALLEL_UPDATES: Final[int] = 0

_LOGGER = logging.getLogger(__name__)

_DEVICE_CLASS_MAP: dict[str, SensorDeviceClass] = {
    "battery": SensorDeviceClass.BATTERY,
    "voltage": SensorDeviceClass.VOLTAGE,
    "current": SensorDeviceClass.CURRENT,
    "temperature": SensorDeviceClass.TEMPERATURE,
    "pressure": SensorDeviceClass.PRESSURE,
    "speed": SensorDeviceClass.SPEED,
    "distance": SensorDeviceClass.DISTANCE,
    "duration": SensorDeviceClass.DURATION,
    "power": SensorDeviceClass.POWER,
    "energy": SensorDeviceClass.ENERGY,
    "volume": SensorDeviceClass.VOLUME,
    "power_factor": SensorDeviceClass.POWER_FACTOR,
}

_STATE_CLASS_MAP: dict[str, SensorStateClass] = {
    "measurement": SensorStateClass.MEASUREMENT,
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
}

_ADAPTER_STATE_OPTIONS = [
    PollingState.OUT_OF_RANGE.value,
    PollingState.CAR_OFF.value,
    PollingState.GRACE_PERIOD.value,
    PollingState.CAR_ON.value,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Elm327ObdiiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Instantiate sensors from the stored profile and clean up orphans."""
    coordinator = entry.runtime_data

    profile = ProfileConfig.from_dict(entry.options[CONF_PROFILE])

    active_standard_keys = {slugify(name) for name in profile.standard_pids}
    active_custom_ids = {pid.id for pid in profile.custom_pids}

    ent_reg = er.async_get(hass)
    existing_entries = er.async_entries_for_config_entry(ent_reg, entry.entry_id)

    prefix_std = f"{entry.unique_id}-std-"
    prefix_custom = f"{entry.unique_id}-custom-"

    for reg_entry in existing_entries:
        if reg_entry.domain != "sensor":
            continue
        uid = reg_entry.unique_id
        if uid.startswith(prefix_std):
            key = uid[len(prefix_std) :]
            if key not in active_standard_keys:
                _LOGGER.info(
                    "Removing orphaned standard sensor: %s", reg_entry.entity_id
                )
                ent_reg.async_remove(reg_entry.entity_id)
        elif uid.startswith(prefix_custom):
            pid_id = uid[len(prefix_custom) :]
            if pid_id not in active_custom_ids:
                _LOGGER.info("Removing orphaned custom sensor: %s", reg_entry.entity_id)
                ent_reg.async_remove(reg_entry.entity_id)

    entities: list[SensorEntity] = []

    for name in profile.standard_pids:
        command = get_standard_command(name)
        if command is None:
            _LOGGER.warning(
                "Standard PID %s not in obdii registry - skipping entity", name
            )
            continue
        entities.append(Elm327ObdiiStandardSensor(coordinator, entry, name, command))

    entities.extend(
        Elm327ObdiiCustomSensor(coordinator, entry, pid) for pid in profile.custom_pids
    )

    entities.append(Elm327ObdiiStateSensor(coordinator, entry))
    entities.append(Elm327ObdiiVoltageSensor(coordinator, entry))

    async_add_entities(entities)


class Elm327ObdiiStandardSensor(Elm327ObdiiEntity, SensorEntity):
    """Sensor for a standard Mode 01 PID."""

    def __init__(
        self,
        coordinator: Elm327ObdiiCoordinator,
        config_entry: Elm327ObdiiConfigEntry,
        command_name: str,
        command: Any,
    ) -> None:
        """Initialize the standard sensor."""
        super().__init__(coordinator, config_entry)
        self._command_name = command_name
        self._command = command
        self._attr_name = " ".join(command.name.replace("_", " ").split()).title()
        self._attr_unique_id = f"{config_entry.unique_id}-std-{slugify(command.name)}"

        units = get_list_of_units(command)
        self._attr_native_unit_of_measurement = units[0] if units else None

        dc_name = propose_device_class(command)
        self._attr_device_class = _DEVICE_CLASS_MAP.get(dc_name) if dc_name else None

        # Only set a custom icon when no device_class is available -
        # HA auto-applies the correct icon based on device_class.
        if self._attr_device_class is None:
            self._attr_icon = propose_icon(command) or "mdi:car"

        sc_name = propose_state_class(command)
        self._attr_state_class = _STATE_CLASS_MAP.get(sc_name) if sc_name else None

    @property
    @override
    def native_value(self) -> StateType:
        """Return the coordinator's stored value, formatting lists for display."""
        data: dict[str, Any] | None = self.coordinator.data
        if data is None:
            return None
        value = data.get(self._command_name)
        return format_sensor_value(value)


class Elm327ObdiiCustomSensor(Elm327ObdiiEntity, SensorEntity):
    """Sensor for a custom PID."""

    def __init__(
        self,
        coordinator: Elm327ObdiiCoordinator,
        config_entry: Elm327ObdiiConfigEntry,
        pid: CustomPid,
    ) -> None:
        """Initialize the custom sensor."""
        super().__init__(coordinator, config_entry)
        self._pid = pid
        self._attr_name = pid.name
        self._attr_unique_id = f"{config_entry.unique_id}-custom-{pid.id}"

        # Enumeration sensors (fmt.map) return strings, not numbers.
        is_enum = bool(pid.fmt.get("map")) if pid.fmt else False

        unit = pid.unit
        if is_enum:
            self._attr_native_unit_of_measurement = None
        else:
            self._attr_native_unit_of_measurement = (
                None if unit in (None, "none", "None") else unit
            )

        if is_enum:
            # Enumerations: set ENUM device class, no state_class, set options.
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_state_class = None
            if pid.fmt and isinstance(pid.fmt.get("map"), dict):
                self._attr_options = sorted(pid.fmt["map"].values(), key=lambda x: x)
        else:
            dc_name = pid.device_class
            if dc_name == "battery" and self._attr_native_unit_of_measurement in (
                "V",
                "v",
                "Volts",
                "volts",
            ):
                self._attr_device_class = SensorDeviceClass.VOLTAGE
            else:
                self._attr_device_class = (
                    _DEVICE_CLASS_MAP.get(dc_name or "") if dc_name else None
                )

            sc_name = pid.state_class
            self._attr_state_class = _STATE_CLASS_MAP.get(sc_name) if sc_name else None
            if self._attr_state_class is None and "ODOMETER" in pid.name.upper():
                self._attr_state_class = SensorStateClass.TOTAL_INCREASING

        extra_attrs: dict[str, float] = {}
        if pid.min_value is not None:
            extra_attrs["min_value"] = pid.min_value
        if pid.max_value is not None:
            extra_attrs["max_value"] = pid.max_value
        if extra_attrs:
            self._attr_extra_state_attributes = extra_attrs

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value computed by the fmt evaluator."""
        data: dict[str, Any] | None = self.coordinator.data
        if data is None:
            return None
        value = data.get(self._pid.id)
        if value is None:
            return None
        # Enumeration sensors return strings directly.
        if isinstance(value, str):
            return value
        try:
            return float(value)
        except TypeError, ValueError:
            return None


class Elm327ObdiiStateSensor(Elm327ObdiiEntity, SensorEntity):
    """Diagnostic sensor tracking the adapter's polling state machine."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = _ADAPTER_STATE_OPTIONS
    _attr_translation_key = "adapter_state"
    _attr_icon = "mdi:car-connected"

    def __init__(
        self,
        coordinator: Elm327ObdiiCoordinator,
        config_entry: Elm327ObdiiConfigEntry,
    ) -> None:
        """Initialize the state sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.unique_id}-adapter-state"

    @property
    @override
    def native_value(self) -> str:
        """Return the current polling state."""
        return self.coordinator.polling_state.value


class Elm327ObdiiVoltageSensor(Elm327ObdiiEntity, SensorEntity):
    """Diagnostic sensor for the 12V battery voltage (from AT RV)."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_translation_key = "battery_voltage"
    _attr_icon = "mdi:car-battery"

    def __init__(
        self,
        coordinator: Elm327ObdiiCoordinator,
        config_entry: Elm327ObdiiConfigEntry,
    ) -> None:
        """Initialize the voltage sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.unique_id}-battery-voltage"

    @property
    @override
    def available(self) -> bool:
        """Go unavailable when there is no voltage reading."""
        return self.coordinator.voltage is not None

    @property
    @override
    def native_value(self) -> StateType:
        """Return the last measured battery voltage."""
        return self.coordinator.voltage
