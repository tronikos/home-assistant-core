"""Dynamic Sensor generation and orphan registry cleanups."""

from collections.abc import Iterable
import logging
from typing import Any

from obdii import Command, Response, commands as veh_commands

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COMMAND, CONF_DEVICE_CLASS, CONF_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify

from .const import (
    CONF_COMMANDS,
    CONF_PROFILE,
    CONF_STATE_CLASS,
    CONF_UNIT,
    ICON_KEYWORDS,
)
from .coordinator import UniversalObdCoordinator
from .entity import UniversalObdEntity
from .wican.profile import WiCanParameter, parse_profile

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_MAP = {
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
}


def propose_icon_from_command(command: Command) -> str:
    """Propose an mdi icon string by checking token suffixes backwards."""
    tokens = command.name.lower().split("_")
    for token in tokens[::-1]:
        if token in ICON_KEYWORDS:
            return ICON_KEYWORDS[token]
    return "mdi:car"


def propose_sensor_state_class(command: Command) -> SensorStateClass | None:
    """Analyze OBD2 metrics using normalized unit collections."""
    if isinstance(command.units, Iterable) and not isinstance(
        command.units, (str, bytes)
    ):
        raw_units = list(command.units)
    elif command.units is not None:
        raw_units = [command.units]
    else:
        raw_units = []

    primary_unit = raw_units[0] if raw_units else None
    tokens = command.name.lower().split("_")
    last_token = tokens[-1] if tokens else ""

    if primary_unit is None or primary_unit in ("string", "bool"):
        return None
    if last_token in ("count", "distance", "time", "odometer"):
        return SensorStateClass.TOTAL_INCREASING
    return SensorStateClass.MEASUREMENT


def get_list_of_units(command: Command) -> list[str]:
    """Get candidate unit structures from command definitions."""
    if isinstance(command.units, Iterable) and not isinstance(
        command.units, (str, bytes)
    ):
        return list(command.units)
    if command.units is not None:
        return [str(command.units)]
    return []


def propose_sensor_device_class(command: Command) -> SensorDeviceClass | None:
    """Analyze OBD2 metrics using normalized unit collections."""
    if isinstance(command.units, Iterable) and not isinstance(
        command.units, (str, bytes)
    ):
        raw_units = list(command.units)
    elif command.units is not None:
        raw_units = [command.units]
    else:
        raw_units = []

    primary_unit = raw_units[0] if raw_units else None
    tokens = command.name.lower().split("_")

    if primary_unit == "°C":
        return SensorDeviceClass.TEMPERATURE
    if primary_unit in ("kPa", "bar", "psi"):
        return SensorDeviceClass.PRESSURE
    if primary_unit in ("V", "v"):
        return SensorDeviceClass.VOLTAGE
    if primary_unit in ("km/h", "mph"):
        return SensorDeviceClass.SPEED
    if primary_unit in ("s", "seconds", "min", "h"):
        return SensorDeviceClass.DURATION
    if "temp" in tokens or "temperature" in tokens:
        return SensorDeviceClass.TEMPERATURE
    # "rpm" removed to avoid triggering SensorDeviceClass.SPEED which demands linear km/h units
    if "speed" in tokens or "velocity" in tokens:
        return SensorDeviceClass.SPEED
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Instantiate and clean up dynamic entities based on standard commands and WiCAN profiles."""
    coordinator: UniversalObdCoordinator = entry.runtime_data

    profile_data = entry.options.get(CONF_PROFILE, "{}")
    profile = parse_profile(profile_data)
    active_wican_parameters = []
    for pid in profile.pids:
        active_wican_parameters.extend(pid.parameters)

    standard_commands_config = entry.options.get(CONF_COMMANDS, [])
    active_standard_commands = []
    for cmd_config in standard_commands_config:
        cmd_name = cmd_config.get(CONF_COMMAND)
        try:
            command = veh_commands[cmd_name]
            active_standard_commands.append((command, cmd_config))
        except KeyError:
            _LOGGER.error("Standard command %s not found, skipping", cmd_name)

    ent_reg = er.async_get(hass)
    existing_entries = er.async_entries_for_config_entry(ent_reg, entry.entry_id)

    active_wican_names = {slugify(p.name) for p in active_wican_parameters}
    active_standard_names = {slugify(cmd[0].name) for cmd in active_standard_commands}

    # Distinct prefix namespaces to prevent overlapping deletions of custom properties
    prefix_wican = f"{entry.unique_id}-wican-"
    prefix_std = f"{entry.unique_id}-std-"

    for reg_entry in existing_entries:
        if reg_entry.domain == "sensor":
            if reg_entry.unique_id.startswith(prefix_std):
                param_name = reg_entry.unique_id[len(prefix_std) :]
                if param_name not in active_standard_names:
                    _LOGGER.info(
                        "Removing orphaned standard sensor: %s", reg_entry.entity_id
                    )
                    ent_reg.async_remove(reg_entry.entity_id)
            elif reg_entry.unique_id.startswith(prefix_wican):
                param_name = reg_entry.unique_id[len(prefix_wican) :]
                if param_name not in active_wican_names:
                    _LOGGER.info(
                        "Removing orphaned WiCAN sensor: %s", reg_entry.entity_id
                    )
                    ent_reg.async_remove(reg_entry.entity_id)

    entities: list[SensorEntity] = [
        *[
            UniversalObdSensor(coordinator, entry, param)
            for param in active_wican_parameters
        ],
        *[
            UniversalObdStandardSensor(coordinator, entry, cmd, cmd_config)
            for cmd, cmd_config in active_standard_commands
        ],
    ]

    async_add_entities(entities)


class UniversalObdSensor(UniversalObdEntity, SensorEntity):
    """Universal OBD Custom WiCAN Sensor representation."""

    def __init__(
        self,
        coordinator: UniversalObdCoordinator,
        config_entry: ConfigEntry,
        parameter: WiCanParameter,
    ) -> None:
        """Initialize sensor with proper classes and attributes."""
        super().__init__(coordinator, config_entry)
        self.parameter = parameter
        self._attr_name = parameter.name
        self._attr_unique_id = (
            f"{config_entry.unique_id}-wican-{slugify(parameter.name)}"
        )
        self._attr_native_unit_of_measurement = (
            parameter.unit if parameter.unit != "none" else None
        )

        if "RPM" in parameter.name.upper() or (
            parameter.unit and "RPM" in parameter.unit.upper()
        ):
            self._attr_device_class = None
        elif (
            parameter.device_class == "battery"
            and self._attr_native_unit_of_measurement in ("V", "v", "Volts", "volts")
        ):
            # Corrects battery assignments with Voltage units that would otherwise fail HA validations
            self._attr_device_class = SensorDeviceClass.VOLTAGE
        else:
            self._attr_device_class = DEVICE_CLASS_MAP.get(parameter.device_class or "")

        if parameter.unit in ("km", "mi") or "ODOMETER" in parameter.name.upper():
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Retrieve computed status from the coordinator."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.parameter.name)


class UniversalObdStandardSensor(UniversalObdEntity, SensorEntity):
    """Standard OBD-II Sensor representation using py-obdii definitions."""

    def __init__(
        self,
        coordinator: UniversalObdCoordinator,
        config_entry: ConfigEntry,
        command: Command,
        config: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry)
        self._command = command
        self._config = config
        self._attr_name = " ".join(command.name.replace("_", " ").split()).capitalize()
        self._attr_unique_id = f"{config_entry.unique_id}-std-{slugify(command.name)}"

        self._attr_icon = config.get(CONF_ICON) or propose_icon_from_command(command)

        # Safely extract single unit representation
        default_units = get_list_of_units(self._command)
        self._attr_native_unit_of_measurement = config.get(CONF_UNIT) or (
            default_units[0] if default_units else None
        )

        dev_cls = config.get(CONF_DEVICE_CLASS)
        if dev_cls:
            try:
                self._attr_device_class = SensorDeviceClass(dev_cls)
            except ValueError:
                _LOGGER.warning(
                    "Invalid device class %s on load, falling back", dev_cls
                )
                self._attr_device_class = propose_sensor_device_class(command)
        else:
            self._attr_device_class = propose_sensor_device_class(command)

        state_cls = config.get(CONF_STATE_CLASS)
        if state_cls:
            try:
                self._attr_state_class = SensorStateClass(state_cls)
            except ValueError:
                _LOGGER.warning(
                    "Invalid state class %s on load, falling back", state_cls
                )
                self._attr_state_class = propose_sensor_state_class(command)
        else:
            self._attr_state_class = propose_sensor_state_class(command)

    async def async_added_to_hass(self) -> None:
        """Register standard command to active collection when active."""
        self.coordinator.active_commands.add(self._command)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Remove standard command from active collection."""
        self.coordinator.active_commands.discard(self._command)
        await super().async_will_remove_from_hass()

    @property
    def native_value(self) -> StateType:
        """Return current parsed value from coordinator data dictionary."""
        if self.coordinator.data is None:
            return None
        response: Response | None = self.coordinator.data.get(str(self._command))
        if response is None:
            return None
        value = response.value
        if isinstance(value, list | tuple):
            if all(isinstance(x, tuple) and len(x) > 0 for x in value):
                return ", ".join(str(x[0]) for x in value)
            return ", ".join(str(item) for item in value)
        return value
