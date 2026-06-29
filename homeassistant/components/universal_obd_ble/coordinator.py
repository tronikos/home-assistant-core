"""Smart Polling Coordinator for OBD2 & WiCAN profiles."""

import contextlib
from datetime import timedelta
import logging
import re
import threading
import time
from typing import Any

from obdii import Command, Connection, Mode, Response, commands as veh_commands

from homeassistant.components.bluetooth import (
    async_address_present,
    async_ble_device_from_address,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ATRV_SUPPORTED,
    CONF_FAST_POLL,
    CONF_GRACE_PERIOD,
    CONF_PROFILE,
    CONF_SLOW_POLL,
    CONF_UUID_READ,
    CONF_UUID_WRITE,
    CONF_VOLTAGE_CHECK,
    CONF_VOLTAGE_OFF,
    CONF_VOLTAGE_ON,
    CONF_XS_POLL,
    DEFAULT_FAST_POLL,
    DEFAULT_GRACE_PERIOD,
    DEFAULT_SLOW_POLL,
    DEFAULT_UUID_READ,
    DEFAULT_UUID_WRITE,
    DEFAULT_VOLTAGE_OFF,
    DEFAULT_VOLTAGE_ON,
    DEFAULT_XS_POLL,
    DOMAIN,
    PollingState,
)
from .obdii.transport_ble import TransportBLE
from .wican.formula import evaluate_wican_expression
from .wican.profile import parse_profile

_LOGGER = logging.getLogger(__name__)

# Matches a plausible vehicle battery voltage: 1-2 digits, decimal point, 1-2 digits.
# e.g. "14.2V", "12.80V".
_VOLTAGE_RE = re.compile(r"(?<!\d)(\d{1,2}\.\d{1,2})(?!\d)")

# Known non-hex diagnostic and error tokens returned by ELM327 interfaces
_OBD_ERROR_TOKENS = ("DATA", "ERROR", "STOPPED", "UNABLE", "BUS")


def extract_dirty_array(raw_response: bytes) -> list[int]:
    """Dump all bytes (including PCI) into a 0-indexed array exactly as the C firmware does.

    Handles space-delimited packets as well as contiguous hex arrays (spaces disabled)
    for standard 11-bit CAN (3 hex chars) and 29-bit CAN (8 hex chars) formats.
    """
    dirty_array = []
    try:
        raw_str = raw_response.decode("utf-8", errors="ignore")
        lines = [
            line.strip()
            for line in raw_str.splitlines()
            if line.strip() and ">" not in line
        ]
        for line in lines:
            if any(token in line for token in _OBD_ERROR_TOKENS):
                continue

            parts = line.split()

            # Fallback for AT S0 (spaces off) returning contiguous hex strings
            if len(parts) == 1 and len(line) > 3:
                token = parts[0]
                # Safely parse 29-bit CAN vs 11-bit without blindly trusting "18" prefixes
                if len(token) > 8 and all(
                    c in "0123456789ABCDEFabcdef" for c in token[:8]
                ):
                    header_len = 8
                else:
                    header_len = 3
                if len(token) > header_len:
                    payload = token[header_len:]
                    parts = [token[:header_len]] + [
                        payload[i : i + 2]
                        for i in range(0, len(payload) - (len(payload) % 2), 2)
                    ]
                    if len(payload) % 2:
                        _LOGGER.debug(
                            "Odd trailing nibble in spaces-off frame: %r", token
                        )

            if len(parts) > 1:
                # First word is the CAN header (e.g., '7E8'). Skip it.
                for part in parts[1:]:
                    try:
                        dirty_array.append(int(part, 16))
                    except ValueError:
                        _LOGGER.debug("Non-hex token in frame, skipping: %r", part)

    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Could not extract dirty array: %s", err)
    return dirty_array


class UniversalObdCoordinator(DataUpdateCoordinator):
    """Local data coordinator coordinating connection state and vehicle metric queries."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator state machine."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=5)
        )
        self.entry = entry
        self.data = {}
        self.state = PollingState.OUT_OF_RANGE
        self.grace_start: float | None = None
        self.api: Connection | None = None
        self._current_init: str | None = None
        self.consecutive_failures = 0
        self.last_successful_poll: float | None = None
        self.last_discovery_attempt: float = 0.0
        self._offline_since: float | None = None
        self.active_commands: set[Command] = set()
        self._supported_pids: list[Any] = []
        self._supported_cmds: list[Any] = []

        # Thread Synchronization lock to prevent race conditions during updates & options flow
        self._lock = threading.Lock()

    def disconnect(self) -> None:
        """Safely close the connection from an executor pool thread."""
        with self._lock:
            if self.api:
                with contextlib.suppress(Exception):
                    self.api.close()
                self.api = None

    @property
    def ble_connected(self) -> bool:
        """Check if BLE is connected."""
        with self._lock:
            return self.api.is_connected() if self.api else False

    @property
    def car_connected(self) -> bool:
        """Verify vehicle responds and has successfully communicated recently."""
        if not self.ble_connected or self.last_successful_poll is None:
            return False
        fast_poll = self.entry.options.get(CONF_FAST_POLL, DEFAULT_FAST_POLL)
        return (time.monotonic() - self.last_successful_poll) < (fast_poll * 2.5 + 5)

    async def async_get_all_pid_commands(
        self, force_refresh: bool = False
    ) -> tuple[list[Any], list[Any]]:
        """Determine and scan all diagnostic commands supported by the vehicle's ECU."""
        if self._supported_pids and self._supported_cmds and not force_refresh:
            return self._supported_pids, self._supported_cmds

        if not self.ble_connected:
            address = self.entry.data[CONF_ADDRESS]
            ble_device = async_ble_device_from_address(self.hass, address, True)
            if ble_device is None:
                raise UpdateFailed(
                    "Connection offline to retrieve supported diagnostic commands"
                )

            connected = await self.hass.async_add_executor_job(
                self._ensure_connected, ble_device
            )
            if not connected:
                raise UpdateFailed("Failed to establish diagnostic standard scan link")

        pids, cmds = await self.hass.async_add_executor_job(
            self._sync_get_all_pid_commands
        )
        self._supported_pids = pids
        self._supported_cmds = cmds
        return pids, cmds

    def _sync_get_all_pid_commands(self) -> tuple[list[Any], list[Any]]:
        """Synchronously request PID support via the executor holding the API lock."""
        with self._lock:
            if not self.api or not self.api.is_connected():
                raise RuntimeError("Vehicle adapter is not actively connected")

            supported_pids = []
            supported_cmds = []

            for cmd_block in (0x00, 0x20, 0x40, 0x60, 0x80, 0xA0, 0xC0):
                try:
                    support_cmd = veh_commands[1][cmd_block]
                    response: Response = self.api.query(support_cmd)
                    if response and isinstance(response.value, list):
                        supported_pids.extend(response.value)
                        for pid in response.value:
                            try:
                                supported_cmds.append(veh_commands[1][pid])
                            except KeyError:
                                _LOGGER.debug(
                                    "PID %s has no library standard definition", pid
                                )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug(
                        "Error retrieving support blocks %s: %s", cmd_block, err
                    )

            return supported_pids, supported_cmds

    async def _async_update_data(self) -> dict[str, Any]:
        """Periodic query trigger."""
        address = self.entry.data[CONF_ADDRESS]
        if not async_address_present(self.hass, address, connectable=True):
            if self._offline_since is None:
                self._offline_since = time.monotonic()

            # Grace period logic before expanding poll interval
            if time.monotonic() - self._offline_since > 60:
                self.state = PollingState.OUT_OF_RANGE
                self.update_interval = timedelta(
                    seconds=self.entry.options.get(CONF_XS_POLL, DEFAULT_XS_POLL)
                )

            # Explicitly raise UpdateFailed so entities report unavailable
            raise UpdateFailed("BLE device out of range")

        self._offline_since = None

        ble_dev = async_ble_device_from_address(self.hass, address, True)
        if ble_dev is None:
            raise UpdateFailed(f"BLE device not found for address {address}")

        # Thread-safe copy of standard commands made on the event loop before thread dispatching
        active_cmds = list(self.active_commands)

        result = await self.hass.async_add_executor_job(
            self._sync_update, ble_dev, active_cmds
        )

        if result.get("failed"):
            raise UpdateFailed(result.get("error", "Polling cycle failed"))

        self.state = result["state"]
        self.update_interval = result["update_interval"]
        self.data = result["data"]
        return self.data

    def _ensure_connected(self, ble_dev) -> bool:
        """Ensure connection to the BLE OBD-II adapter is active. Lock must be held by caller."""
        if self.api and self.api.is_connected():
            return True

        self.last_discovery_attempt = time.monotonic()

        if self.api:
            with contextlib.suppress(Exception):
                self.api.close()

        transport = None
        try:
            transport = TransportBLE(
                ble_device=ble_dev,
                loop=self.hass.loop,
                uuid_write=self.entry.options.get(
                    CONF_UUID_WRITE,
                    self.entry.data.get(CONF_UUID_WRITE, DEFAULT_UUID_WRITE),
                ),
                uuid_read=self.entry.options.get(
                    CONF_UUID_READ,
                    self.entry.data.get(CONF_UUID_READ, DEFAULT_UUID_READ),
                ),
                timeout=4.0,
            )
            self.api = Connection(transport)
            self._current_init = None
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("Connection failed: %s", e)
            if transport is not None:
                with contextlib.suppress(Exception):
                    transport.close()
            self.api = None
            return False
        else:
            return True

    def _extract_voltage(self, raw_text: str) -> float | None:
        """Safely parse voltage numeric floats from AT RV raw response."""
        match = _VOLTAGE_RE.search(raw_text)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def _handle_voltage_check(self, fast_interval: timedelta) -> tuple[str, timedelta]:
        """Query battery voltage and determine the operational polling state and interval."""
        voltage_check_enabled = self.entry.options.get(CONF_VOLTAGE_CHECK, True)
        if not (self.entry.data.get(CONF_ATRV_SUPPORTED) and voltage_check_enabled):
            return PollingState.CAR_ON, fast_interval

        assert self.api is not None
        rv_resp: Response[Any] = self.api.query(Command(Mode.AT, "RV"))
        if not rv_resp or not rv_resp.raw:
            _LOGGER.debug("Empty or invalid RV response received")
            return PollingState.CAR_ON, fast_interval

        raw_text = rv_resp.raw.decode(errors="ignore")
        voltage = self._extract_voltage(raw_text)
        if voltage is None:
            _LOGGER.debug(
                "Could not parse numeric voltage from RV response: %r", raw_text
            )
            return PollingState.CAR_ON, fast_interval

        off_threshold = self.entry.options.get(CONF_VOLTAGE_OFF, DEFAULT_VOLTAGE_OFF)
        on_threshold = self.entry.options.get(CONF_VOLTAGE_ON, DEFAULT_VOLTAGE_ON)
        grace_seconds = self.entry.options.get(CONF_GRACE_PERIOD, DEFAULT_GRACE_PERIOD)

        is_running = (
            voltage >= on_threshold
            if self.state == PollingState.CAR_OFF
            else voltage >= off_threshold
        )

        if is_running:
            self.grace_start = None
            return PollingState.CAR_ON, fast_interval

        if self.state == PollingState.CAR_OFF:
            return PollingState.CAR_OFF, timedelta(
                seconds=self.entry.options.get(CONF_SLOW_POLL, DEFAULT_SLOW_POLL)
            )

        if self.grace_start is None:
            self.grace_start = time.monotonic()

        if time.monotonic() - self.grace_start > grace_seconds:
            return PollingState.CAR_OFF, timedelta(
                seconds=self.entry.options.get(CONF_SLOW_POLL, DEFAULT_SLOW_POLL)
            )

        return PollingState.GRACE_PERIOD, fast_interval

    def _run_queries(self, res_data: dict[str, Any]) -> bool:
        """Execute the configured profile PID queries. Return True if any succeed."""
        assert self.api is not None

        profile = parse_profile(self.entry.options.get(CONF_PROFILE, {}))
        any_success = False

        if not self._current_init and profile.init:
            for c in profile.init.split(";"):
                if c:
                    self.api.transport.write_bytes(c.encode() + b"\r")
                    self.api.transport.read_bytes()
            self._current_init = "GLOBAL"

        # Sort PIDs by pid_init so all PIDs sharing the same CAN header /
        # init string are polled consecutively to avoid slow BLE round-trips.
        sorted_pids = sorted(profile.pids, key=lambda p: (p.pid_init or "", p.command))

        for pid in sorted_pids:
            if pid.pid_init and pid.pid_init != self._current_init:
                for c in pid.pid_init.split(";"):
                    if c:
                        self.api.transport.write_bytes(c.encode() + b"\r")
                        self.api.transport.read_bytes()
                self._current_init = pid.pid_init

            if len(pid.command) >= 2:
                cmd: Command[Any] = Command(pid.command[:2], pid.command[2:])
                resp: Response[Any] = self.api.query(cmd)
                if resp and resp.raw:
                    if b"BUFFER FULL" in resp.raw:
                        continue

                    dirty_array = extract_dirty_array(resp.raw)
                    if not dirty_array:
                        continue

                    for param in pid.parameters:
                        val = evaluate_wican_expression(param.expression, dirty_array)
                        if val is not None:
                            res_data[param.name] = val
                            any_success = True

        return any_success

    def _sync_update(self, ble_dev, active_cmds: list[Command]) -> dict[str, Any]:
        """Thread-safe update cycle executed inside the executor pool."""
        with self._lock:
            res_state = self.state
            res_interval = self.update_interval
            res_data = dict(self.data)

            if not self._ensure_connected(ble_dev):
                self.consecutive_failures += 1
                return {"failed": True, "error": "Connection to OBD adapter failed"}

            assert self.api is not None

            try:
                fast_interval = timedelta(
                    seconds=self.entry.options.get(CONF_FAST_POLL, DEFAULT_FAST_POLL)
                )

                # Voltage Gate Protection
                res_state, res_interval = self._handle_voltage_check(fast_interval)

                if res_state == PollingState.CAR_OFF:
                    self.consecutive_failures = 0
                    return {
                        "data": res_data,
                        "state": res_state,
                        "update_interval": res_interval,
                        "failed": False,
                    }

                standard_success = False

                # Run Standard active commands
                for cmd in active_cmds:
                    try:
                        resp = self.api.query(cmd)
                        if resp and resp.value is not None:
                            res_data[str(cmd)] = resp
                            standard_success = True
                    except Exception as e:  # noqa: BLE001
                        _LOGGER.debug("Failed updating standard command %s: %s", cmd, e)

                # Run custom profile WiCAN queries
                profile_data = self.entry.options.get(CONF_PROFILE)
                profile_success = False
                if profile_data and profile_data != "{}":
                    profile_success = self._run_queries(res_data)

                if standard_success or profile_success:
                    self.last_successful_poll = time.monotonic()

                self.consecutive_failures = 0

            except Exception as e:  # noqa: BLE001
                _LOGGER.warning(
                    "Error during polling cycle, resetting connection: %s", e
                )
                with contextlib.suppress(Exception):
                    self.api.close()
                self.api = None
                self._current_init = None
                self.consecutive_failures += 1
                return {"failed": True, "error": str(e)}

            return {
                "data": res_data,
                "state": res_state,
                "update_interval": res_interval,
                "failed": False,
            }
