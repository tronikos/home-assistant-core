"""Constants for the ELM327 OBD-II BLE integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "elm327_obdii_ble"

PLATFORMS: Final[list[Platform]] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONF_ATRV_SUPPORTED: Final = "atrv_supported"

CONF_UUID_READ: Final = "uuid_read"
CONF_UUID_WRITE: Final = "uuid_write"

DEFAULT_UUID_READ: Final = "0000fff1-0000-1000-8000-00805f9b34fb"
DEFAULT_UUID_WRITE: Final = "0000fff2-0000-1000-8000-00805f9b34fb"

CONF_PROFILE: Final = "profile"

CONF_VOLTAGE_CHECK: Final = "voltage_check"
CONF_VOLTAGE_ON: Final = "voltage_on_threshold"
CONF_VOLTAGE_OFF: Final = "voltage_off_threshold"
CONF_GRACE_PERIOD: Final = "voltage_grace_seconds"

# Polling intervals are NOT user-configurable (per the HA integration
# quality scale guidelines). These fixed values are tuned for the
# battery-protection state machine in the coordinator:
#   - FAST: CAR_ON / GRACE_PERIOD - catch transient state changes
#   - SLOW: CAR_OFF - ECU is asleep, just check voltage occasionally
#   - OUT_OF_RANGE: adapter not seen for >60s - rare connection sweep
FAST_POLL_SECONDS: Final = 5
SLOW_POLL_SECONDS: Final = 300
OUT_OF_RANGE_POLL_SECONDS: Final = 3600

DEFAULT_VOLTAGE_ON: Final = 13.1
DEFAULT_VOLTAGE_OFF: Final = 12.8
DEFAULT_GRACE_PERIOD: Final = 30

DEBOUNCE_COOLDOWN: Final = 60
