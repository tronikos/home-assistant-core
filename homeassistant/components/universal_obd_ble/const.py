"""Constants for Universal OBD BLE."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "universal_obd_ble"

PLATFORMS: Final[list[Platform]] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONF_PROFILE: Final = "profile"
CONF_VOLTAGE_CHECK: Final = "voltage_check"
CONF_FAST_POLL: Final = "fast_poll"
CONF_SLOW_POLL: Final = "slow_poll"
CONF_XS_POLL: Final = "xs_poll"
CONF_VOLTAGE_ON: Final = "voltage_on_threshold"
CONF_VOLTAGE_OFF: Final = "voltage_off_threshold"
CONF_GRACE_PERIOD: Final = "voltage_grace_seconds"
CONF_ATRV_SUPPORTED: Final = "atrv_supported"

CONF_UUID_READ: Final = "uuid_read"
CONF_UUID_WRITE: Final = "uuid_write"

CONF_COMMANDS: Final = "commands"
CONF_UNIT: Final = "unit"
CONF_STATE_CLASS: Final = "state_class"

DEFAULT_UUID_READ: Final = "0000fff1-0000-1000-8000-00805f9b34fb"
DEFAULT_UUID_WRITE: Final = "0000fff2-0000-1000-8000-00805f9b34fb"

DEFAULT_FAST_POLL: Final = 5
DEFAULT_SLOW_POLL: Final = 300
DEFAULT_XS_POLL: Final = 3600
DEFAULT_VOLTAGE_ON: Final = 13.1
DEFAULT_VOLTAGE_OFF: Final = 12.8
DEFAULT_GRACE_PERIOD: Final = 30

DEBOUNCE_COOLDOWN: Final = 60


class PollingState:
    """States of the vehicle polling coordinator."""

    OUT_OF_RANGE = "out_of_range"
    CAR_ON = "car_on"
    GRACE_PERIOD = "grace_period"
    CAR_OFF = "car_off"


ICON_KEYWORDS: Final[dict[str, str]] = {
    "rpm": "mdi:engine",
    "speed": "mdi:speedometer",
    "velocity": "mdi:speedometer",
    "temp": "mdi:thermometer",
    "temperature": "mdi:thermometer",
    "coolant": "mdi:thermometer",
    "voltage": "mdi:sine-wave",
    "volt": "mdi:sine-wave",
    "v": "mdi:sine-wave",
    "battery": "mdi:battery",
    "current": "mdi:current-ac",
    "pressure": "mdi:gauge",
    "bar": "mdi:gauge",
    "psi": "mdi:gauge",
    "kpa": "mdi:gauge",
    "vacuum": "mdi:gauge-empty",
    "fuel": "mdi:gas-station",
    "ethanol": "mdi:gas-station",
    "rate": "mdi:gas-station-outline",
    "level": "mdi:water-percent",
    "ratio": "mdi:aspect-ratio",
    "equivalence": "mdi:aspect-ratio",
    "maf": "mdi:air-filter",
    "flow": "mdi:air-filter",
    "air": "mdi:air-conditioner",
    "throttle": "mdi:speedometer",
    "egr": "mdi:pipe-valve",
    "sensor": "mdi:leak",
    "sensors": "mdi:leak",
    "o2": "mdi:molecule",
    "nox": "mdi:smog",
    "particulate": "mdi:scooter",
    "dpf": "mdi:smoke-detector-alert",
    "catalyst": "mdi:factory",
    "time": "mdi:clock-outline",
    "runtime": "mdi:timer-outline",
    "count": "mdi:counter",
    "counters": "mdi:counter",
    "distance": "mdi:map-marker-distance",
    "mil": "mdi:engine-outline",
    "odometer": "mdi:counter",
    "load": "mdi:weight",
    "torque": "mdi:wrench",
    "trim": "mdi:tune",
    "trims": "mdi:tune",
    "advance": "mdi:angle-acute",
    "vin": "mdi:card-account-details",
    "id": "mdi:identifier",
    "cvn": "mdi:shield-check",
    "dtc": "mdi:alert-octagon",
    "clear": "mdi:alert-circle-check",
}
