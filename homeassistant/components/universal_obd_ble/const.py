"""Constants for Universal OBD BLE.

Refactored to use the UOPS (Unified OBD Parameter Schema). The old
CONF_PROFILE (raw WiCAN JSON string) and CONF_COMMANDS (list of
per-PID config dicts) are gone - replaced by CONF_UOPS, which holds
the whole tracked set in our internal format.

Per-PID icon/unit/device_class/state_class overrides for standard PIDs
are no longer stored here - users customize standard-PID entities via
Home Assistant's native entity settings panel. Custom PIDs carry their
own metadata in the UOPS structure (see uops/schema.py).
"""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "universal_obd_ble"

PLATFORMS: Final[list[Platform]] = [Platform.BINARY_SENSOR, Platform.SENSOR]

# ---------------------------------------------------------------------------
# Config entry data (immutable after setup) - device-level facts
# ---------------------------------------------------------------------------

CONF_ATRV_SUPPORTED: Final = "atrv_supported"  # adapter answers AT RV (in entry.data)

CONF_UUID_READ: Final = "uuid_read"
CONF_UUID_WRITE: Final = "uuid_write"

DEFAULT_UUID_READ: Final = "0000fff1-0000-1000-8000-00805f9b34fb"
DEFAULT_UUID_WRITE: Final = "0000fff2-0000-1000-8000-00805f9b34fb"

# ---------------------------------------------------------------------------
# Config entry options (editable via options flow)
# ---------------------------------------------------------------------------

CONF_UOPS: Final = "uops"  # dict matching uops.UopsConfig.to_dict()

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

# Debounce for BLE re-discovery callback - prevents connection loops
# during advertisement storms.
DEBOUNCE_COOLDOWN: Final = 60


# ---------------------------------------------------------------------------
# Polling state machine
# ---------------------------------------------------------------------------


class PollingState:
    """States of the vehicle polling coordinator.

    OUT_OF_RANGE - BLE adapter not seen for >60s; polling at xs_poll.
    CAR_ON       - voltage above threshold; polling at fast_poll.
    GRACE_PERIOD - voltage dropped; holding fast_poll for grace_seconds.
    CAR_OFF      - voltage stayed low; polling at slow_poll.
    """

    OUT_OF_RANGE = "out_of_range"
    CAR_ON = "car_on"
    GRACE_PERIOD = "grace_period"
    CAR_OFF = "car_off"
