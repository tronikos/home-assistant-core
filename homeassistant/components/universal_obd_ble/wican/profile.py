"""Profile parsing utility functions for dynamic profile load."""

from dataclasses import dataclass, field
import json
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


@dataclass
class WiCanParameter:
    """WiCAN Param schema."""

    name: str
    expression: str
    unit: str | None = None
    device_class: str | None = None
    min_value: float | None = None
    max_value: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WiCanParameter:
        """Build from dictionary."""
        return cls(
            name=data.get("name") or data.get("short_name") or "",
            expression=data.get("expression") or "",
            unit=data.get("unit"),
            device_class=data.get("class"),
            min_value=float(data["min"]) if data.get("min") is not None else None,
            max_value=float(data["max"]) if data.get("max") is not None else None,
        )


@dataclass
class WiCanPid:
    """WiCAN PID schema."""

    command: str
    pid_init: str | None = None
    parameters: list[WiCanParameter] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WiCanPid:
        """Build from dictionary."""
        raw_params = data.get("parameters") or []
        parameters = []
        if isinstance(raw_params, list):
            parameters = [WiCanParameter.from_dict(p) for p in raw_params]
        elif isinstance(raw_params, dict):
            for name, expr in raw_params.items():
                parameters.append(WiCanParameter(name=name, expression=expr))
        return cls(
            command=data.get("pid") or "",
            pid_init=data.get("pid_init"),
            parameters=parameters,
        )


@dataclass
class WiCanProfile:
    """WiCAN Profile dataclass container."""

    car_model: str
    init: str | None = None
    pids: list[WiCanPid] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WiCanProfile:
        """Build from dictionary."""
        pids = [WiCanPid.from_dict(p) for p in data.get("pids", [])]
        return cls(
            car_model=data.get("car_model") or "",
            init=data.get("init"),
            pids=pids,
        )


def parse_profile(profile_source: Any) -> WiCanProfile:
    """Parses profile data safely from a JSON string or raw dictionary."""
    if isinstance(profile_source, str):
        try:
            profile_source = json.loads(profile_source)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to parse profile JSON string: %s", err)
            profile_source = {}

    if not isinstance(profile_source, dict):
        profile_source = {}

    return WiCanProfile.from_dict(profile_source)
