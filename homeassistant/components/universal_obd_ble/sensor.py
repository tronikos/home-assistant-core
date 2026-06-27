"""Dynamic Sensor generation and orphan registry cleanups."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from .const import CONF_PROFILE
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Instantiate and clean up dynamic entities based on active JSON profile config."""
    coordinator: UniversalObdCoordinator = entry.runtime_data
    profile_data = entry.options.get(CONF_PROFILE, "{}")
    profile = parse_profile(profile_data)

    active_parameters: list[WiCanParameter] = []
    for pid in profile.pids:
        active_parameters.extend(pid.parameters)

    # Clean up registered entities that are no longer part of the parsed profile
    ent_reg = er.async_get(hass)
    existing_entries = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    active_names = {slugify(p.name) for p in active_parameters}

    # Format: {unique_id}-{slugify(parameter.name)}
    prefix = f"{entry.unique_id}-"
    for reg_entry in existing_entries:
        if reg_entry.domain == "sensor" and reg_entry.unique_id.startswith(prefix):
            param_name = reg_entry.unique_id[len(prefix) :]
            if param_name not in active_names:
                _LOGGER.info(
                    "Removing orphaned integration entity: %s", reg_entry.entity_id
                )
                ent_reg.async_remove(reg_entry.entity_id)

    # Add active entities
    sensors = [
        UniversalObdSensor(coordinator, entry, param) for param in active_parameters
    ]
    async_add_entities(sensors)


class UniversalObdSensor(UniversalObdEntity, SensorEntity):
    """Universal OBD Sensor representation."""

    def __init__(
        self,
        coordinator: UniversalObdCoordinator,
        config_entry,
        parameter: WiCanParameter,
    ) -> None:
        """Initialize sensor with proper classes and attributes."""
        super().__init__(coordinator, config_entry)
        self.parameter = parameter
        self._attr_name = parameter.name
        self._attr_unique_id = f"{config_entry.unique_id}-{slugify(parameter.name)}"
        self._attr_native_unit_of_measurement = (
            parameter.unit if parameter.unit != "none" else None
        )

        # RPM Special Case Gating
        if "RPM" in parameter.name.upper() or (
            parameter.unit and "RPM" in parameter.unit.upper()
        ):
            self._attr_device_class = None
        else:
            self._attr_device_class = DEVICE_CLASS_MAP.get(parameter.device_class or "")

        # State Class Assignment
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
