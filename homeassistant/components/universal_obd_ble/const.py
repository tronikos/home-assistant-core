"""Constants for Universal OBD BLE."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "universal_obd_ble"

PLATFORMS: Final[list[Platform]] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONF_ATRV_SUPPORTED: Final = "atrv_supported"

CONF_UUID_READ: Final = "uuid_read"
CONF_UUID_WRITE: Final = "uuid_write"

DEFAULT_UUID_READ: Final = "0000fff1-0000-1000-8000-00805f9b34fb"
DEFAULT_UUID_WRITE: Final = "0000fff2-0000-1000-8000-00805f9b34fb"

CONF_UOPS: Final = "uops"

CONF_VOLTAGE_CHECK: Final = "voltage_check"
CONF_FAST_POLL: Final = "fast_poll"
CONF_SLOW_POLL: Final = "slow_poll"
CONF_XS_POLL: Final = "xs_poll"
CONF_VOLTAGE_ON: Final = "voltage_on_threshold"
CONF_VOLTAGE_OFF: Final = "voltage_off_threshold"
CONF_GRACE_PERIOD: Final = "voltage_grace_seconds"

DEFAULT_FAST_POLL: Final = 5
DEFAULT_SLOW_POLL: Final = 300
DEFAULT_XS_POLL: Final = 3600
DEFAULT_VOLTAGE_ON: Final = 13.1
DEFAULT_VOLTAGE_OFF: Final = 12.8
DEFAULT_GRACE_PERIOD: Final = 30

DEBOUNCE_COOLDOWN: Final = 60
