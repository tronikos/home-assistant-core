"""Sensor platform for the ELM327 OBD-II BLE integration."""

import logging
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify

from .const import CONF_PROFILE
from .coordinator import Elm327ObdiiCoordinator
from .elm327_obdii import (
    CustomPid,
    ProfileConfig,
    format_sensor_value,
    get_list_of_units,
    get_standard_command,
    propose_device_class,
    propose_icon,
    propose_state_class,
)
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
        self._attr_name = " ".join(command.name.replace("_", " ").split()).capitalize()
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

        unit = pid.unit
        self._attr_native_unit_of_measurement = (
            None if unit in (None, "none", "None") else unit
        )

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
        if self._attr_state_class is None:
            name_upper = pid.name.upper()
            if "ODOMETER" in name_upper or unit in ("km", "mi"):
                self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            else:
                self._attr_state_class = SensorStateClass.MEASUREMENT

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
        data: dict[str, Any] | None = self.coordinator.data
        if data is None:
            return None
        value = data.get(self._pid.name)
        if value is None:
            return None
        try:
            return float(value)
        except TypeError, ValueError:
            return None
