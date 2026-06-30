"""Polling coordinator for Universal OBD BLE.

Refactored to use the UOPS library. The coordinator no longer:
  - parses WiCAN JSON on every poll cycle
  - walks AST trees on every poll cycle
  - tracks CAN-header state with two independent loops (standard
    vs custom) that leak stale headers across cycles

Instead it builds a single `query_plan` once at startup (rebuilt on
options reload) by combining standard Mode 01 commands and custom
PIDs into one ordered list of (CanContext, [QueryItem]) groups. Each
poll tick walks the plan in order, switching ATSH/ATCRA only when
the context changes BETWEEN groups - including transitioning back
to the default (header=None) context, which fixes the stale-header
bug where standard PIDs silently inherited a custom PID's header
filter from the previous cycle.

Voltage gating, battery-guard state machine, BLE-out-of-range sweep,
and the synchronous executor dispatch are preserved from the
pre-refactor design - those concerns are orthogonal to the UOPS work.
"""

import contextlib
from datetime import timedelta
import logging
import threading
import time
from typing import Any

from obdii import Command, Connection, Mode, Response

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
    CONF_SLOW_POLL,
    CONF_UOPS,
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
from .uops import (
    CanContext,
    CustomQueryItem,
    QueryItem,
    StandardQueryItem,
    UopsConfig,
    build_query_plan,
    context_for_custom_pid,
    extract_voltage,
    get_standard_command,
    make_evaluator,
    scan_supported_pids,
)

_LOGGER = logging.getLogger(__name__)


class UniversalObdCoordinator(DataUpdateCoordinator):
    """Local data coordinator that runs a pre-built UOPS query plan."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator state machine."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=5)
        )
        self.entry = entry
        self.data: dict[str, Any] = {}
        self.state = PollingState.OUT_OF_RANGE
        self.grace_start: float | None = None
        self.api: Connection | None = None
        self._current_context: CanContext | None = None
        self.consecutive_failures = 0
        self.last_successful_poll: float | None = None
        self.last_discovery_attempt: float = 0.0
        self._offline_since: float | None = None

        # The query plan - built once at startup from entry.options[CONF_UOPS].
        # Rebuilt on options reload (the entry is fully reloaded by
        # update_options_listener in __init__.py, so a fresh coordinator
        # instance gets a fresh plan).
        self._query_plan: list[tuple[CanContext, list[QueryItem]]] = []
        self._build_query_plan()

        # Thread synchronization lock - held for the entire _sync_update
        # cycle to prevent the options flow's PID scan from interleaving
        # with a poll tick.
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Query plan construction
    # ------------------------------------------------------------------

    def _build_query_plan(self) -> None:
        """Turn entry.options[CONF_UOPS] into an ordered list of (context, items).

        Standard Mode 01 PIDs and custom PIDs are combined into a
        single plan grouped by CAN context. The default context
        (header=None) always comes first, so standard PIDs run before
        any ATSH reconfiguration - and the plan naturally transitions
        back to default at the start of every cycle.
        """
        uops_dict = self.entry.options.get(CONF_UOPS, {})
        uops = UopsConfig.from_dict(uops_dict)

        items: list[QueryItem] = []

        for name in uops.standard_pids:
            command = get_standard_command(name)
            if command is None:
                _LOGGER.warning(
                    "Standard PID %s not found in obdii registry - skipping", name
                )
                continue
            items.append(StandardQueryItem(command_name=name, command=command))

        for pid in uops.custom_pids:
            try:
                # Pass expected_bytes so py-obdii can use the ELM327
                # early-return optimization (appends a return-digit to
                # the query so the adapter returns as soon as it has
                # the expected number of response lines, instead of
                # waiting for the full timeout). 0 = disabled.
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

        self._query_plan = build_query_plan(items)
        _LOGGER.debug(
            "Built query plan: %d items in %d groups",
            sum(len(g) for _, g in self._query_plan),
            len(self._query_plan),
        )

    # ------------------------------------------------------------------
    # Public properties used by binary_sensor.py
    # ------------------------------------------------------------------

    @property
    def ble_connected(self) -> bool:
        """True if the BLE link to the adapter is up."""
        with self._lock:
            return self.api.is_connected() if self.api else False

    @property
    def car_connected(self) -> bool:
        """True if the vehicle responded recently."""
        if not self.ble_connected or self.last_successful_poll is None:
            return False
        fast_poll = self.entry.options.get(CONF_FAST_POLL, DEFAULT_FAST_POLL)
        return (time.monotonic() - self.last_successful_poll) < (fast_poll * 2.5 + 5)

    def disconnect(self) -> None:
        """Safely close the connection from an executor pool thread."""
        with self._lock:
            if self.api:
                with contextlib.suppress(Exception):
                    self.api.close()
                self.api = None
                self._current_context = None

    # ------------------------------------------------------------------
    # Supported-PID scan (used by the options flow's standard-PID multiselect)
    # ------------------------------------------------------------------

    async def async_scan_supported_standard_pids(self) -> list[str]:
        """Live-scan the ECU for supported Mode 01 PIDs.

        Used by the options flow's standard-PID multiselect to filter
        the dropdown to only PIDs the car actually supports. Opens a
        connection if needed, runs the bitmap walk, returns canonical
        command names.
        """
        if not self.ble_connected:
            address = self.entry.data[CONF_ADDRESS]
            ble_device = async_ble_device_from_address(self.hass, address, True)
            if ble_device is None:
                raise UpdateFailed(
                    "BLE adapter not in range - cannot scan supported PIDs"
                )
            connected = await self.hass.async_add_executor_job(
                self._ensure_connected, ble_device
            )
            if not connected:
                raise UpdateFailed("Failed to connect for supported-PID scan")

        return await self.hass.async_add_executor_job(self._sync_scan_supported_pids)

    def _sync_scan_supported_pids(self) -> list[str]:
        """Run the bitmap walk holding the API lock."""
        with self._lock:
            if not self.api or not self.api.is_connected():
                raise UpdateFailed("Adapter not connected during supported-PID scan")
            return scan_supported_pids(self.api)

    # ------------------------------------------------------------------
    # Main polling cycle
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Periodic query trigger."""
        address = self.entry.data[CONF_ADDRESS]
        if not async_address_present(self.hass, address, connectable=True):
            if self._offline_since is None:
                self._offline_since = time.monotonic()
            # Grace period before expanding poll interval - keeps the
            # entity responsive through brief BLE dropouts.
            if time.monotonic() - self._offline_since > 60:
                self.state = PollingState.OUT_OF_RANGE
                self.update_interval = timedelta(
                    seconds=self.entry.options.get(CONF_XS_POLL, DEFAULT_XS_POLL)
                )
            raise UpdateFailed("BLE device out of range")

        self._offline_since = None

        ble_dev = async_ble_device_from_address(self.hass, address, True)
        if ble_dev is None:
            raise UpdateFailed(f"BLE device not found for address {address}")

        # Snapshot the plan on the event loop - the options flow could
        # otherwise mutate it mid-cycle if a reload interleaves.
        plan = list(self._query_plan)

        result = await self.hass.async_add_executor_job(
            self._sync_update, ble_dev, plan
        )

        if result.get("failed"):
            raise UpdateFailed(result.get("error", "Polling cycle failed"))

        self.state = result["state"]
        self.update_interval = result["update_interval"]
        self.data = result["data"]
        return self.data

    def _sync_update(
        self,
        ble_dev,
        plan: list[tuple[CanContext, list[QueryItem]]],
    ) -> dict[str, Any]:
        """Thread-safe update cycle executed inside the executor pool."""
        with self._lock:
            res_state = self.state
            res_interval = self.update_interval
            res_data: dict[str, Any] = dict(self.data)

            if not self._ensure_connected(ble_dev):
                self.consecutive_failures += 1
                return {"failed": True, "error": "Connection to OBD adapter failed"}

            assert self.api is not None

            try:
                fast_interval = timedelta(
                    seconds=self.entry.options.get(CONF_FAST_POLL, DEFAULT_FAST_POLL)
                )

                # Voltage gate - may transition to CAR_OFF and skip the query plan.
                res_state, res_interval = self._handle_voltage_check(fast_interval)

                if res_state != PollingState.CAR_OFF:
                    any_success = self._run_plan(plan, res_data)
                    if any_success:
                        self.last_successful_poll = time.monotonic()

                self.consecutive_failures = 0

            except Exception as e:  # noqa: BLE001
                _LOGGER.warning(
                    "Error during polling cycle, resetting connection: %s", e
                )
                with contextlib.suppress(Exception):
                    self.api.close()
                self.api = None
                self._current_context = None
                self.consecutive_failures += 1
                return {"failed": True, "error": str(e)}

            return {
                "data": res_data,
                "state": res_state,
                "update_interval": res_interval,
                "failed": False,
            }

    def _run_plan(
        self,
        plan: list[tuple[CanContext, list[QueryItem]]],
        res_data: dict[str, Any],
    ) -> bool:
        """Walk the query plan, switching CAN context only between groups.

        Returns True if at least one query succeeded. The plan is
        ordered with the default context first, so standard Mode 01
        PIDs always run before any ATSH reconfiguration - and the
        plan naturally transitions back to default at the start of
        every cycle, which fixes the stale-header bug.
        """
        assert self.api is not None
        any_success = False

        for context, items in plan:
            # Transition context only when it actually changes. This is
            # the literal "group and sort by CAN headers to minimize
            # slow ELM327 initialization delays" requirement.
            if context != self._current_context:
                self._apply_can_context(context)
                self._current_context = context

            for item in items:
                try:
                    value = item.execute(self.api)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Query %s failed: %s", item.key, err)
                    continue
                if value is not None:
                    res_data[item.key] = value
                    any_success = True

        return any_success

    def _apply_can_context(self, context: CanContext) -> None:
        """Send the AT commands needed to transition to `context`.

        Sends ATSH (set header), ATCRA (set receive address), and any
        extra AT commands the context carries. For the default context
        (all None), this is a no-op - the adapter retains whatever
        addressing it had, which is fine because standard Mode 01
        queries use functional broadcast 7DF and don't depend on a
        specific receive filter.

        Note: clearing ATCRA back to "no filter" requires `ATCRA` with
        no argument on most ELM327 firmware. We don't issue that here
        because the standard Mode 01 responses come back on the
        default broadcast receive path and an explicit ATCRA filter
        would suppress them. If a user's vehicle needs ATCRA cleared
        between groups, they can put `ATCRA` (no arg) in the next
        custom PID's `init_extra` field.
        """
        assert self.api is not None
        transport = self.api.transport

        if context.header is not None:
            self._send_at(transport, f"ATSH{context.header}")

        if context.filter is not None:
            self._send_at(transport, f"ATCRA{context.filter}")

        if context.extra_init:
            for cmd in context.extra_init.split(";"):
                cmd = cmd.strip()
                if cmd:
                    self._send_at(transport, cmd)

    def _send_at(self, transport, command: str) -> None:
        """Write a single AT command + CR, then drain the response.

        The ELM327 acknowledges AT commands with `OK` (or sometimes
        just `>`). We don't parse the ack - we just drain up to the
        prompt so the next query starts with a clean buffer.
        """
        try:
            transport.write_bytes(command.encode() + b"\r")
            transport.read_bytes()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("AT command %r failed: %s", command, err)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _ensure_connected(self, ble_dev) -> bool:
        """Ensure the BLE OBD-II adapter connection is active.

        Lock must be held by the caller. Creates a fresh TransportBLE
        + Connection if needed; resets the CAN-context cache so the
        next poll cycle re-applies the default context explicitly.
        """
        if self.api and self.api.is_connected():
            return True

        self.last_discovery_attempt = time.monotonic()

        if self.api:
            with contextlib.suppress(Exception):
                self.api.close()
            self.api = None
            self._current_context = None

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
            # Force re-application of the default context on the next
            # poll - the plan's first group is always default, but
            # setting _current_context to None makes the comparison
            # explicit so we don't skip it.
            self._current_context = None
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("Connection failed: %s", e)
            if transport is not None:
                with contextlib.suppress(Exception):
                    transport.close()
            self.api = None
            return False
        return True

    # ------------------------------------------------------------------
    # Voltage gate / battery guard
    # ------------------------------------------------------------------

    def _handle_voltage_check(self, fast_interval: timedelta) -> tuple[str, timedelta]:
        """Query battery voltage and determine the polling state + interval.

        Hysteresis: `on_threshold` is used to wake from CAR_OFF;
        `off_threshold` is used otherwise. A grace period keeps
        fast polling for `grace_seconds` after the voltage first
        drops, so brief dips during crank don't immediately sleep.
        """
        voltage_check_enabled = self.entry.options.get(CONF_VOLTAGE_CHECK, True)
        if not (self.entry.data.get(CONF_ATRV_SUPPORTED) and voltage_check_enabled):
            return PollingState.CAR_ON, fast_interval

        assert self.api is not None
        rv_resp: Response[Any] = self.api.query(Command(Mode.AT, "RV"))
        if not rv_resp or not rv_resp.raw:
            _LOGGER.debug("Empty or invalid RV response received")
            return PollingState.CAR_ON, fast_interval

        voltage = extract_voltage(rv_resp.raw)
        if voltage is None:
            _LOGGER.debug(
                "Could not parse numeric voltage from RV response: %r",
                rv_resp.raw.decode(errors="ignore"),
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
