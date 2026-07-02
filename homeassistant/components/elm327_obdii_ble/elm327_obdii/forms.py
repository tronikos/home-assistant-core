"""Config-flow form-building helpers.

These produce plain dicts (not HA voluptuous schemas or selectors) so
the library stays HA-agnostic. The HA config flow wraps them in
``vol.Schema`` and ``selector.SelectSelector`` as needed.
"""

from typing import Any

from obdii import commands as veh_commands

from ._core.elm327_parsing import as_float
from ._core.schema import CustomPid
from ._core.standard_pids import get_standard_command, is_supported_pids_bitmap


def all_known_standard_pid_names() -> list[str]:
    """Every standard Mode 01 PID name the obdii registry knows about.

    Excludes the SUPPORTED_PIDS_A..G bitmap commands (metadata, not
    user-trackable parameters) and any "Unnamed" command entries.
    """
    names: list[str] = []
    for cmd in veh_commands[1]:
        if cmd.name == "Unnamed":
            continue
        if is_supported_pids_bitmap(cmd.name):
            continue
        names.append(cmd.name)
    return names


def standard_pid_options(command_names: list[str]) -> list[dict[str, str]]:
    """Build the standard-PID multiselect options sorted by name.

    Returns a list of ``{"value": name, "label": "NAME (mode pid)"}`` dicts.
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
    """Pre-fill the edit form from an existing :class:`CustomPid`."""
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


def user_input_to_form_defaults(user_input: dict[str, Any]) -> dict[str, Any]:
    """Build form defaults from submitted user input (preserves on validation error)."""
    return {
        "pid_name": user_input.get("pid_name", ""),
        "mode": (user_input.get("mode") or "").strip().upper(),
        "query": (user_input.get("query") or "").strip().upper(),
        "can_header": (user_input.get("can_header") or "").strip().upper(),
        "can_filter": (user_input.get("can_filter") or "").strip().upper(),
        "init_extra": user_input.get("init_extra", ""),
        "formula": (user_input.get("formula") or "").strip(),
        "unit": user_input.get("unit", ""),
        "device_class": user_input.get("device_class", ""),
        "state_class": user_input.get("state_class", ""),
        "min_value": as_float(user_input.get("min_value")),
        "max_value": as_float(user_input.get("max_value")),
        "expected_bytes": int(user_input.get("expected_bytes") or 0),
    }
