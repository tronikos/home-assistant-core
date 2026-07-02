"""Polling state machine, voltage gate, and query-plan execution.

The :class:`Poller` façade owns the per-config query plan, the polling
state machine, the CAN-context cursor, and the BLE connection. Callers
(the HA coordinator) drive it via :meth:`Poller.connect`,
:meth:`Poller.poll_once`, :meth:`Poller.disconnect`, and
:meth:`Poller.scan_supported_standard_pids`.

This collapses what used to be three separate library calls
(plan-building, voltage check, plan execution) plus a hand-threaded
CAN-context cursor into a single object that owns the cross-cycle
state internally.
"""

import asyncio
import contextlib
from dataclasses import dataclass, field
from enum import StrEnum
import logging
import threading
import time
from typing import Any

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from obdii import Command, Connection, Mode, Response
from obdii.transports.transport_base import TransportBase

from ._core.can_context import CanContext, context_for_custom_pid
from ._core.elm327_parsing import extract_voltage
from ._core.formula import make_evaluator
from ._core.query_items import (
    CustomQueryItem,
    QueryItem,
    StandardQueryItem,
    build_query_plan,
)
from ._core.schema import ProfileConfig
from ._core.standard_pids import get_standard_command, scan_supported_pids
from .transport_ble import TransportBLE, TransportError

_LOGGER = logging.getLogger(__name__)


class PollingState(StrEnum):
    """States of the vehicle polling state machine."""

    OUT_OF_RANGE = "out_of_range"
    CAR_ON = "car_on"
    GRACE_PERIOD = "grace_period"
    CAR_OFF = "car_off"


@dataclass(frozen=True)
class PollerConfig:
    """Static configuration for a :class:`Poller`.

    Built once from a config entry's data + options; the Poller reads
    it on every cycle. Voltage thresholds protect the vehicle's 12V
    auxiliary battery - when voltage drops below ``voltage_off`` for
    longer than ``grace_seconds``, the poller transitions to
    :attr:`PollingState.CAR_OFF` and the coordinator slows its poll
    interval accordingly.
    """

    profile: ProfileConfig
    atrv_supported: bool
    voltage_check_enabled: bool
    voltage_on: float
    voltage_off: float
    grace_seconds: int


@dataclass
class PollResult:
    """One polling cycle's outcome.

    The coordinator reads ``state`` to pick the next ``update_interval``
    and ``data`` to populate ``coordinator.data``. ``voltage`` is
    exposed for diagnostics.
    """

    state: PollingState
    data: dict[str, Any] = field(default_factory=dict)
    any_success: bool = False
    voltage: float | None = None


class Poller:
    """Owns: query plan, CAN-context cursor, polling state machine, BLE connection.

    Thread-safe via an internal :class:`threading.Lock` - all public
    methods may be called from the executor pool while the event loop
    reads :attr:`state` and :attr:`is_connected` concurrently.
    """

    def __init__(self, config: PollerConfig) -> None:
        """Build the query plan and initialize state to OUT_OF_RANGE."""
        self._config = config
        self._query_plan = _build_query_plan_from_profile(config.profile)
        self._current_context: CanContext | None = None
        self._state: PollingState = PollingState.OUT_OF_RANGE
        self._grace_start: float | None = None
        self._consecutive_failures = 0
        self._last_successful_poll: float | None = None
        self._api: Connection | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> PollingState:
        """Current polling state. Lock-free read; safe from the event loop."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """True if the BLE link to the adapter is up.

        Lock-free read; safe from the event loop. May lag the executor
        thread's view by up to one poll cycle.
        """
        return self._api is not None and self._api.is_connected()

    @property
    def consecutive_failures(self) -> int:
        """Number of consecutive failed poll cycles since the last success."""
        return self._consecutive_failures

    def connect(
        self,
        ble_device: BLEDevice,
        loop: asyncio.AbstractEventLoop,
        uuid_write: str,
        uuid_read: str,
        timeout: float = 4.0,
    ) -> bool:
        """Open (or reuse) the BLE connection to the adapter. Returns success.

        Idempotent: if a connection is already alive, returns True
        immediately. On failure, closes any stale handle and returns
        False (no exception raised - the caller decides what to do).
        """
        with self._lock:
            if self._api is not None and self._api.is_connected():
                return True
            if self._api is not None:
                with contextlib.suppress(BleakError, OSError, TransportError):
                    self._api.close()
                self._api = None
                self._current_context = None
            self._api = _create_connection(
                ble_device, loop, uuid_write, uuid_read, timeout
            )
            if self._api is None:
                return False
            self._current_context = None
            return True

    def disconnect(self) -> None:
        """Close the BLE connection if open. Safe to call repeatedly."""
        with self._lock:
            if self._api is not None:
                with contextlib.suppress(BleakError, OSError, TransportError):
                    self._api.close()
                self._api = None
                self._current_context = None

    def poll_once(self) -> PollResult:
        """Run one polling cycle. Caller must have connected first.

        On transport failure, resets the connection, increments the
        failure counter, and returns a :class:`PollResult` preserving
        the previous state. Does NOT raise - the coordinator decides
        whether to surface this as :class:`UpdateFailed`.
        """
        with self._lock:
            if self._api is None or not self._api.is_connected():
                self._consecutive_failures += 1
                return PollResult(state=self._state)

            try:
                new_state, voltage = self._check_voltage()
                self._state = new_state

                data: dict[str, Any] = {}
                any_success = False
                if new_state != PollingState.CAR_OFF:
                    data, any_success, self._current_context = _run_query_plan(
                        self._api, self._query_plan, self._current_context
                    )
                    if any_success:
                        self._last_successful_poll = time.monotonic()

                self._consecutive_failures = 0
                return PollResult(
                    state=new_state, data=data, any_success=any_success, voltage=voltage
                )

            except (
                BleakError,
                TimeoutError,
                OSError,
                ConnectionError,
                TransportError,
            ) as err:
                _LOGGER.warning(
                    "Error during polling cycle, resetting connection: %s", err
                )
                with contextlib.suppress(BleakError, OSError, TransportError):
                    self._api.close()
                self._api = None
                self._current_context = None
                self._consecutive_failures += 1
                return PollResult(state=self._state)

    def scan_supported_standard_pids(self) -> list[str]:
        """Walk the ECU's Mode 01 PID bitmaps and return supported command names.

        Caller must have connected first. Raises :class:`RuntimeError`
        if called while disconnected (the coordinator maps this to an
        :class:`UpdateFailed`).
        """
        with self._lock:
            if self._api is None or not self._api.is_connected():
                raise RuntimeError("Adapter not connected - cannot scan supported PIDs")
            return scan_supported_pids(self._api)

    def _check_voltage(self) -> tuple[PollingState, float | None]:
        """Query battery voltage via AT RV and advance the state machine.

        Assumes ``self._api`` is connected. Returns the new state plus
        the parsed voltage (None if the response was unreadable or the
        voltage check is disabled).
        """
        cfg = self._config
        if not (cfg.atrv_supported and cfg.voltage_check_enabled):
            return PollingState.CAR_ON, None

        # Caller (poll_once) guarantees self._api is connected; narrow for mypy.
        assert self._api is not None
        rv_resp: Response[Any] = self._api.query(Command(Mode.AT, "RV"))
        if not rv_resp or not rv_resp.raw:
            _LOGGER.debug("Empty or invalid RV response received")
            return PollingState.CAR_ON, None

        voltage = extract_voltage(rv_resp.raw)
        if voltage is None:
            _LOGGER.debug(
                "Could not parse numeric voltage from RV response: %r",
                rv_resp.raw.decode(errors="ignore"),
            )
            return PollingState.CAR_ON, None

        # Hysteresis: the threshold for "engine started" (on_threshold) is
        # higher than for "engine still running" (off_threshold), so a
        # brief voltage dip during crank doesn't immediately drop us to
        # CAR_OFF.
        is_running = (
            voltage >= cfg.voltage_on
            if self._state == PollingState.CAR_OFF
            else voltage >= cfg.voltage_off
        )

        if is_running:
            self._grace_start = None
            return PollingState.CAR_ON, voltage

        if self._state == PollingState.CAR_OFF:
            return PollingState.CAR_OFF, voltage

        if self._grace_start is None:
            self._grace_start = time.monotonic()

        if time.monotonic() - self._grace_start > cfg.grace_seconds:
            return PollingState.CAR_OFF, voltage

        return PollingState.GRACE_PERIOD, voltage


def _build_query_plan_from_profile(
    profile: ProfileConfig,
) -> list[tuple[CanContext, list[QueryItem]]]:
    """Combine standard + custom PIDs into a context-grouped query plan."""
    items: list[QueryItem] = []

    for name in profile.standard_pids:
        command = get_standard_command(name)
        if command is None:
            _LOGGER.warning(
                "Standard PID %s not found in obdii registry - skipping", name
            )
            continue
        items.append(StandardQueryItem(command_name=name, command=command))

    for pid in profile.custom_pids:
        try:
            command = Command(
                pid.mode,
                pid.query,
                expected_bytes=pid.expected_bytes or 0,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Could not build obdii.Command for custom PID %s (mode=%s query=%s): %s",
                pid.name,
                pid.mode,
                pid.query,
                err,
            )
            continue
        try:
            evaluator = make_evaluator(pid.formula)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Custom PID %s has invalid formula %r - skipping: %s",
                pid.name,
                pid.formula,
                err,
            )
            continue
        items.append(
            CustomQueryItem(
                pid=pid,
                command=command,
                evaluator=evaluator,
                context=context_for_custom_pid(pid),
            )
        )

    return build_query_plan(items)


def _create_connection(
    ble_dev: BLEDevice,
    loop: asyncio.AbstractEventLoop,
    uuid_write: str,
    uuid_read: str,
    timeout: float = 4.0,
) -> Connection | None:
    """Create a TransportBLE + Connection. Returns None on failure."""
    transport: TransportBLE | None = None
    try:
        transport = TransportBLE(
            ble_device=ble_dev,
            loop=loop,
            uuid_write=uuid_write,
            uuid_read=uuid_read,
            timeout=timeout,
        )
        return Connection(transport)
    except (BleakError, TimeoutError, OSError, TransportError) as e:
        _LOGGER.warning("Connection failed: %s", e)
        if transport is not None:
            with contextlib.suppress(BleakError, OSError, TransportError):
                transport.close()
        return None


def _apply_can_context(transport: TransportBase, context: CanContext) -> None:
    """Send the AT commands needed to transition to ``context``."""
    if context.header is not None:
        _send_at(transport, f"ATSH{context.header}")
    if context.filter is not None:
        _send_at(transport, f"ATCRA{context.filter}")
    if context.extra_init:
        for cmd in context.extra_init.split(";"):
            cmd = cmd.strip()
            if cmd:
                _send_at(transport, cmd)


def _send_at(transport: TransportBase, command: str) -> None:
    """Write a single AT command + CR, then drain the response."""
    try:
        transport.write_bytes(command.encode() + b"\r")
        transport.read_bytes()
    except (OSError, TimeoutError, TransportError) as err:
        _LOGGER.debug("AT command %r failed: %s", command, err)


def _run_query_plan(
    api: Connection,
    plan: list[tuple[CanContext, list[QueryItem]]],
    current_context: CanContext | None,
) -> tuple[dict[str, Any], bool, CanContext | None]:
    """Walk the query plan, switching CAN context only between groups.

    Returns ``(data, any_success, new_current_context)``.
    """
    res_data: dict[str, Any] = {}
    any_success = False
    ctx = current_context

    for context, items in plan:
        if context != ctx:
            _apply_can_context(api.transport, context)
            ctx = context

        for item in items:
            try:
                value = item.execute(api)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Query %s failed: %s", item.key, err)
                continue
            if value is not None:
                res_data[item.key] = value
                any_success = True

    return res_data, any_success, ctx
