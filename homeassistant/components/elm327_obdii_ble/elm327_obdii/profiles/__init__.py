"""Built-in vehicle profiles in UOPS internal format.

Original works - not derivatives of any upstream GPL-licensed profile
database. CAN PID addresses are factual data (not copyrightable);
formulas use UOPS canonical notation; the JSON schema is ProfileConfig.

For a wider selection, the integration fetches WiCAN's
vehicle_profiles.json at runtime and translates it via
`uops.importers.wican.import_wican_profile`. Nothing from the source
JSON is persisted or redistributed; only the resulting ProfileConfig is
stored in the user's HA config entry.
"""

from importlib import resources
import json
from typing import Any

from ..schema import CustomPid, ProfileConfig


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


def load_builtin_profile(name: str) -> ProfileConfig | None:
    """Return the named built-in profile as a ProfileConfig, or None if not found.

    Name match is exact and case-sensitive. Built-in profile names are
    defined in builtin.json and are stable across releases - adding a
    new profile is safe, renaming an existing one would orphan user
    entity unique-ids.
    """
    for entry in list_builtin_profiles():
        if entry.get("name") == name:
            return _entry_to_profile(entry)
    return None


def _entry_to_profile(entry: dict[str, Any]) -> ProfileConfig:
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
    return ProfileConfig(standard_pids=standard, custom_pids=custom)
