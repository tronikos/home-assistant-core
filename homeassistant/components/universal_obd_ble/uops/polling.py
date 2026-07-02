"""Polling state machine, voltage gate, and query-plan execution.

Pure-Python polling logic with no Home Assistant imports. The
coordinator delegates to these functions for the parts that don't
need HA's DataUpdateCoordinator coupling.
"""

import asyncio
import contextlib
from datetime import timedelta
from enum import StrEnum
import logging
import time
from typing import Any

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from obdii import Command, Connection, Mode, Response
from obdii.transports.transport_base import TransportBase

from .compiler import make_evaluator
from .helpers import extract_voltage
from .scheduler import (
    CanContext,
    CustomQueryItem,
    QueryItem,
    StandardQueryItem,
    build_query_plan,
    context_for_custom_pid,
)
from .schema import UopsConfig
from .standard_pids import get_standard_command
from .transport_ble import TransportBLE, TransportError

_LOGGER = logging.getLogger(__name__)


class PollingState(StrEnum):
    """States of the vehicle polling coordinator."""

    OUT_OF_RANGE = "out_of_range"
    CAR_ON = "car_on"
    GRACE_PERIOD = "grace_period"
    CAR_OFF = "car_off"


def build_query_plan_from_uops(
    uops: UopsConfig,
) -> list[tuple[CanContext, list[QueryItem]]]:
    """Build an ordered query plan from a UopsConfig.

    Standard Mode 01 PIDs and custom PIDs are combined into a single
    plan grouped by CAN context. The default context (header=None)
    always comes first.
    """
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


def create_connection(
    ble_dev: BLEDevice,
    loop: asyncio.AbstractEventLoop,
    uuid_write: str,
    uuid_read: str,
    timeout: float = 4.0,
) -> Connection | None:
    """Create a TransportBLE + Connection. Returns None on failure."""
    transport = None
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


def apply_can_context(transport: TransportBase, context: CanContext) -> None:
    """Send the AT commands needed to transition to `context`."""
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


def run_query_plan(
    api: Connection,
    plan: list[tuple[CanContext, list[QueryItem]]],
    current_context: CanContext | None,
) -> tuple[dict[str, Any], bool, CanContext | None]:
    """Walk the query plan, switching CAN context only between groups.

    Returns (data, any_success, new_current_context).
    """
    res_data: dict[str, Any] = {}
    any_success = False
    ctx = current_context

    for context, items in plan:
        if context != ctx:
            apply_can_context(api.transport, context)
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


def check_voltage(
    api: Connection,
    atrv_supported: bool,
    voltage_check_enabled: bool,
    on_threshold: float,
    off_threshold: float,
    grace_seconds: int,
    current_state: PollingState,
    grace_start: float | None,
) -> tuple[PollingState, timedelta | None, float | None]:
    """Query battery voltage and determine the polling state + interval.

    Returns (state, interval_or_None, new_grace_start).
    interval is None if the caller should use its fast_poll default.
    """
    if not (atrv_supported and voltage_check_enabled):
        return PollingState.CAR_ON, None, None

    rv_resp: Response[Any] = api.query(Command(Mode.AT, "RV"))
    if not rv_resp or not rv_resp.raw:
        _LOGGER.debug("Empty or invalid RV response received")
        return PollingState.CAR_ON, None, grace_start

    voltage = extract_voltage(rv_resp.raw)
    if voltage is None:
        _LOGGER.debug(
            "Could not parse numeric voltage from RV response: %r",
            rv_resp.raw.decode(errors="ignore"),
        )
        return PollingState.CAR_ON, None, grace_start

    is_running = (
        voltage >= on_threshold
        if current_state == PollingState.CAR_OFF
        else voltage >= off_threshold
    )

    if is_running:
        return PollingState.CAR_ON, None, None

    if current_state == PollingState.CAR_OFF:
        return PollingState.CAR_OFF, None, grace_start

    if grace_start is None:
        grace_start = time.monotonic()

    if time.monotonic() - grace_start > grace_seconds:
        return PollingState.CAR_OFF, None, grace_start

    return PollingState.GRACE_PERIOD, None, grace_start
