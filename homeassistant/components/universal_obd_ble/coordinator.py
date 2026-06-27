"""Smart Polling Coordinator for OBD2 & WiCAN profiles."""

import contextlib
from datetime import timedelta
import logging
import re
import time
from typing import Any

from obdii import Command, Connection, Mode, Response

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.components.bluetooth.api import async_address_present
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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
                if (
                    len(token) > 8
                    and token.upper().startswith("18")
                    and all(c in "0123456789ABCDEFabcdef" for c in token)
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

    @property
    def ble_connected(self) -> bool:
        """Check if BLE is connected."""
        return self.api.is_connected() if self.api else False

    @property
    def car_connected(self) -> bool:
        """Check if the car is actively communicating."""
        return self.ble_connected and self.state in (
            PollingState.CAR_ON,
            PollingState.GRACE_PERIOD,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Periodic query trigger."""
        address = self.entry.data[CONF_ADDRESS]
        if not async_address_present(self.hass, address, connectable=True):
            self.state = PollingState.OUT_OF_RANGE
            self.update_interval = timedelta(
                seconds=self.entry.options.get(CONF_XS_POLL, DEFAULT_XS_POLL)
            )
            return self.data

        # Thread-safe BLE device resolution on the main event loop
        ble_dev = async_ble_device_from_address(self.hass, address, True)
        if ble_dev is None:
            _LOGGER.warning("BLE device not found for address %s", address)
            return self.data

        # Safely execute blocking tasks in executor and apply states on the event loop
        result = await self.hass.async_add_executor_job(self._sync_update, ble_dev)

        self.state = result["state"]
        self.update_interval = result["update_interval"]
        self.data = result["data"]
        return self.data

    def _ensure_connected(self, ble_dev) -> bool:
        """Ensure connection to the BLE OBD-II adapter is active."""
        if self.api and self.api.is_connected():
            return True

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

        # Determine if car is running based on protective hysteresis
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

        if not self.grace_start:
            self.grace_start = time.monotonic()

        if time.monotonic() - self.grace_start > grace_seconds:
            return PollingState.CAR_OFF, timedelta(
                seconds=self.entry.options.get(CONF_SLOW_POLL, DEFAULT_SLOW_POLL)
            )

        return PollingState.GRACE_PERIOD, fast_interval

    def _run_queries(self, res_data: dict[str, Any]) -> None:
        """Execute the configured profile PID queries."""
        assert self.api is not None

        profile = parse_profile(self.entry.options.get(CONF_PROFILE, {}))

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

    def _sync_update(self, ble_dev) -> dict[str, Any]:
        """Thread-safe synchronous updates executing inside executor thread pool."""
        res_state = self.state
        res_interval = self.update_interval
        res_data = dict(self.data)

        if not self._ensure_connected(ble_dev):
            return {
                "data": res_data,
                "state": res_state,
                "update_interval": res_interval,
            }

        assert self.api is not None

        try:
            fast_interval = timedelta(
                seconds=self.entry.options.get(CONF_FAST_POLL, DEFAULT_FAST_POLL)
            )

            # 1. Voltage Gate Protection
            res_state, res_interval = self._handle_voltage_check(fast_interval)

            if res_state == PollingState.CAR_OFF:
                return {
                    "data": res_data,
                    "state": res_state,
                    "update_interval": res_interval,
                }

            # 2. Execute Queries
            self._run_queries(res_data)

            self.last_successful_poll = time.monotonic()
            self.consecutive_failures = 0

        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("Error during polling cycle, resetting connection: %s", e)
            if self.api:
                with contextlib.suppress(Exception):
                    self.api.close()
            self.api = None
            self._current_init = None
            self.consecutive_failures += 1

        return {"data": res_data, "state": res_state, "update_interval": res_interval}
