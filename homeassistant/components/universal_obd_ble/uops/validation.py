"""Validation helpers and form-building utilities for the config flow.

Pure-Python helpers with no Home Assistant imports. The config flow
calls these for hex validation, float coercion, and standard-PID
option building.
"""

from typing import Any

from obdii import commands as veh_commands

from .schema import CustomPid
from .standard_pids import get_standard_command


def is_hex(s: str) -> bool:
    """True if s is a non-empty string of hex digits."""
    if not s:
        return False
    try:
        int(s, 16)
    except ValueError:
        return False
    return True


def as_float(v: Any) -> float | None:
    """Coerce v to float, returning None on failure or empty input."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except TypeError, ValueError:
        return None


def all_known_standard_pid_names() -> list[str]:
    """Every standard Mode 01 PID name the obdii registry knows about."""
    names: list[str] = []
    for cmd in veh_commands[1]:
        if cmd.name == "Unnamed":
            continue
        if cmd.name.startswith("SUPPORTED_PIDS"):
            continue
        names.append(cmd.name)
    return names


def standard_pid_options(command_names: list[str]) -> list[dict[str, str]]:
    """Build the standard-PID multiselect options sorted by name.

    Returns a list of {"value": name, "label": "NAME (mode pid)"} dicts.
    """
    options: list[dict[str, str]] = []
    for name in sorted(command_names):
        cmd = get_standard_command(name)
        if cmd is None:
            continue
        label = f"{name} ({cmd.mode} {cmd.pid})"
        options.append({"value": name, "label": label})
    return options


def pid_to_form_defaults(pid: CustomPid) -> dict[str, Any]:
    """Pre-fill the edit form from an existing CustomPid."""
    return {
        "pid_name": pid.name,
        "mode": pid.mode,
        "query": pid.query,
        "can_header": pid.can_header or "",
        "can_filter": pid.can_filter or "",
        "init_extra": pid.init_extra or "",
        "formula": pid.formula,
        "unit": pid.unit or "",
        "device_class": pid.device_class or "",
        "state_class": pid.state_class or "",
        "min_value": pid.min_value,
        "max_value": pid.max_value,
        "expected_bytes": pid.expected_bytes or 0,
    }


def empty_form_defaults() -> dict[str, Any]:
    """Defaults for a brand-new custom PID form."""
    return {
        "pid_name": "",
        "mode": "22",
        "query": "",
        "can_header": "",
        "can_filter": "",
        "init_extra": "",
        "formula": "B(0)",
        "unit": "",
        "device_class": "",
        "state_class": "",
        "min_value": None,
        "max_value": None,
        "expected_bytes": 0,
    }


def format_sensor_value(value: Any) -> str | int | float | None:
    """Format a standard-PID resolver value for HA state display.

    Lists are joined into comma-separated strings; everything else
    is returned as-is.
    """
    if value is None:
        return None
    if isinstance(value, list | tuple):
        if all(isinstance(x, tuple) and len(x) > 0 for x in value):
            return ", ".join(str(x[0]) for x in value)
        return ", ".join(str(item) for item in value)
    if isinstance(value, (int, float, str)):
        return value
    return str(value)
