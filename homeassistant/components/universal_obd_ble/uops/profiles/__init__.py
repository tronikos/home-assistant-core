"""Built-in vehicle profiles in UOPS internal format.

These are original works authored by the integration maintainers -
NOT derivatives of any upstream GPL-licensed profile database.

  - The CAN PID addresses (e.g. "028C1" for VW e-Golf SOC) are factual
    data about the vehicles' CAN buses - facts are not copyrightable
    in any jurisdiction.
  - The formulas are expressed in UOPS canonical notation designed
    specifically for this integration (B(n), B(n:m), S(n), S(n:m),
    BIT(b, n)) - not copied from WiCAN's `[B5:B6]` notation.
  - The JSON schema is the UopsConfig schema designed for this
    integration - not the WiCAN profile schema.

For a wider selection of vehicle profiles, the integration fetches
WiCAN's vehicle_profiles.json at runtime from meatpiHQ/wican-fw and
translates it via `uops.importers.wican.import_wican_profile`. That
runtime fetch + transform is OK license-wise: nothing from the source
JSON is persisted or redistributed; only the resulting UopsConfig is
stored in the user's HA config entry.
"""

from importlib import resources
import json
from typing import Any

from ..schema import CustomPid, UopsConfig


def list_builtin_profiles() -> list[dict[str, Any]]:
    """Return the raw list of built-in profile entries (with name/description).

    Each entry has at minimum: name, description, standard_pids, custom_pids.
    Use this to populate the vehicle-selection dropdown in the config flow.
    """
    with (
        resources.files(__package__)
        .joinpath("builtin.json")
        .open("r", encoding="utf-8") as f
    ):
        data = json.load(f)
    return list(data.get("profiles", []))


def load_builtin_profile(name: str) -> UopsConfig | None:
    """Return the named built-in profile as a UopsConfig, or None if not found.

    Name match is exact and case-sensitive. Built-in profile names are
    defined in builtin.json and are stable across releases - adding a
    new profile is safe, renaming an existing one would orphan user
    entity unique-ids.
    """
    for entry in list_builtin_profiles():
        if entry.get("name") == name:
            return _entry_to_uops(entry)
    return None


def _entry_to_uops(entry: dict[str, Any]) -> UopsConfig:
    standard = list(entry.get("standard_pids", []))
    custom: list[CustomPid] = []
    for cp_dict in entry.get("custom_pids", []):
        # Built-in profiles use stable string IDs (e.g. "egolf-soc-bms")
        # so entity unique-ids don't change across HA restarts or
        # integration upgrades. If a built-in entry is missing `id`,
        # fall back to a name-derived slug - but every entry in
        # builtin.json should have one.
        if "id" not in cp_dict:
            continue
        custom.append(CustomPid.from_dict(cp_dict))
    return UopsConfig(standard_pids=standard, custom_pids=custom)
