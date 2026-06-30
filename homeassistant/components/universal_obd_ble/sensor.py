"""Sensor platform for Universal OBD BLE.

Refactored to be a thin entity factory. Per-PID icon/unit/device_class
heuristic logic has moved into uops/standard_pids.py; per-entity
display customization (rename, icon override, unit override) is
handled by Home Assistant's native entity settings panel, not stored
in our config entry.

Two entity classes:

  - UniversalObdStandardSensor — for standard Mode 01 PIDs from
    uops.standard_pids. Uses uops heuristics for icon/device_class/
    state_class/units. The coordinator stores the resolver's typed
    value (float, int, list, str); this sensor formats lists/tuples
    into comma-joined strings for display.

  - UniversalObdCustomSensor — for custom PIDs from uops.custom_pids.
    Uses the per-PID metadata carried in the UOPS structure
    (unit/device_class/state_class set by the user in the Master-Detail
    options screen). The coordinator stores a float (or None) for
    each custom PID.

Orphan entity cleanup: when the user removes a PID from the UOPS,
the corresponding entity is removed from the entity registry. Stable
ids on CustomPid mean renaming a PID's display name keeps its
history; only deleting the PID orphans the entity.
"""

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify

from .const import CONF_UOPS
from .coordinator import UniversalObdCoordinator
from .entity import UniversalObdEntity
from .uops import (
    CustomPid,
    UopsConfig,
    get_list_of_units,
    get_standard_command,
    propose_device_class,
    propose_icon,
    propose_state_class,
)

_LOGGER = logging.getLogger(__name__)

# Maps the string names returned by uops.propose_device_class (and the
# device_class field on CustomPid) to HA's SensorDeviceClass enum.
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

# Maps the string names returned by uops.propose_state_class to HA's
# SensorStateClass enum.
_STATE_CLASS_MAP: dict[str, SensorStateClass] = {
    "measurement": SensorStateClass.MEASUREMENT,
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Instantiate sensors from UOPS and clean up orphans."""
    coordinator: UniversalObdCoordinator = entry.runtime_data

    uops = UopsConfig.from_dict(entry.options.get(CONF_UOPS, {}))

    # Build the set of active unique-id suffixes for orphan cleanup.
    active_standard_keys = {slugify(name) for name in uops.standard_pids}
    active_custom_ids = {pid.id for pid in uops.custom_pids}

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

    for name in uops.standard_pids:
        command = get_standard_command(name)
        if command is None:
            _LOGGER.warning(
                "Standard PID %s not in obdii registry — skipping entity", name
            )
            continue
        entities.append(UniversalObdStandardSensor(coordinator, entry, name, command))

    entities.extend(
        UniversalObdCustomSensor(coordinator, entry, pid) for pid in uops.custom_pids
    )

    async_add_entities(entities)


class UniversalObdStandardSensor(UniversalObdEntity, SensorEntity):
    """Sensor for a standard Mode 01 PID.

    Icon, device_class, state_class, and unit are proposed by
    uops/standard_pids.py heuristics from the obdii Command object.
    Users override any of these via HA's native entity settings panel.
    """

    def __init__(
        self,
        coordinator: UniversalObdCoordinator,
        config_entry: ConfigEntry,
        command_name: str,
        command: Any,
    ) -> None:
        """Initialize the standard sensor."""
        super().__init__(coordinator, config_entry)
        self._command_name = command_name
        self._command = command
        self._attr_name = " ".join(command.name.replace("_", " ").split()).capitalize()
        self._attr_unique_id = f"{config_entry.unique_id}-std-{slugify(command.name)}"

        self._attr_icon = propose_icon(command) or "mdi:car"

        units = get_list_of_units(command)
        self._attr_native_unit_of_measurement = units[0] if units else None

        dc_name = propose_device_class(command)
        self._attr_device_class = _DEVICE_CLASS_MAP.get(dc_name) if dc_name else None

        sc_name = propose_state_class(command)
        self._attr_state_class = _STATE_CLASS_MAP.get(sc_name) if sc_name else None

    @property
    def native_value(self) -> StateType:
        """Return the coordinator's stored value, formatting lists for display."""
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get(self._command_name)
        return _format_value(value)


class UniversalObdCustomSensor(UniversalObdEntity, SensorEntity):
    """Sensor for a custom PID.

    Unit, device_class, state_class, icon, min, max all come from the
    CustomPid dataclass in the UOPS — set by the user in the options
    flow's Master-Detail custom PID editor. The coordinator stores a
    float (or None) per custom PID.
    """

    def __init__(
        self,
        coordinator: UniversalObdCoordinator,
        config_entry: ConfigEntry,
        pid: CustomPid,
    ) -> None:
        """Initialize the custom sensor."""
        super().__init__(coordinator, config_entry)
        self._pid = pid
        self._attr_name = pid.name
        # Stable id keyed on pid.id — renaming the display name does
        # NOT orphan the entity. Only deleting the PID does.
        self._attr_unique_id = f"{config_entry.unique_id}-custom-{pid.id}"

        # Treat the literal string "none" as no unit (matches the
        # pre-refactor behavior where users typed "none" in the unit
        # field to suppress the unit display).
        unit = pid.unit
        self._attr_native_unit_of_measurement = (
            None if unit in (None, "none", "None") else unit
        )

        dc_name = pid.device_class
        # Special case: a "battery" device_class with a voltage unit
        # must be exposed as VOLTAGE or HA validation rejects it.
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
        if self._attr_state_class is None:
            # Default: counters/odometers are total_increasing; everything else measurement.
            name_upper = pid.name.upper()
            if "ODOMETER" in name_upper or unit in ("km", "mi"):
                self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            else:
                self._attr_state_class = SensorStateClass.MEASUREMENT

        # Expose min_value / max_value as extra state attributes so
        # frontend gauge cards can use them for range visualization.
        # NOTE: _attr_native_min_value / _attr_native_max_value are
        # NumberEntity properties, NOT SensorEntity — setting them on
        # a SensorEntity is a silent no-op (HA ignores unknown _attr_*
        # assignments). Extra state attributes are the correct channel
        # for exposing advisory metadata on a sensor.
        extra_attrs: dict[str, float] = {}
        if pid.min_value is not None:
            extra_attrs["min_value"] = pid.min_value
        if pid.max_value is not None:
            extra_attrs["max_value"] = pid.max_value
        if extra_attrs:
            self._attr_extra_state_attributes = extra_attrs

    @property
    def native_value(self) -> StateType:
        """Return the float value computed by the compiled formula."""
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get(self._pid.name)
        if value is None:
            return None
        try:
            return float(value)
        except TypeError, ValueError:
            return None


def _format_value(value: Any) -> StateType:
    """Format a standard-PID resolver value for HA state display.

    obdii resolvers return:
      - float / int  for most PIDs (RPM, speed, temp, ...)
      - list[int]    for supported-PID bitmaps
      - list[tuple]  for O2 sensor voltage+trim pairs, fuel system status
      - str          for DTCs, VIN
      - None         when the query failed

    Lists are joined into comma-separated strings; everything else
    is returned as-is (HA will str() it for state).
    """
    if value is None:
        return None
    if isinstance(value, list | tuple):
        if all(isinstance(x, tuple) and len(x) > 0 for x in value):
            return ", ".join(str(x[0]) for x in value)
        return ", ".join(str(item) for item in value)
    if isinstance(value, (int, float, str)):
        return value
    return str(value)
