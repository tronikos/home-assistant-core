"""WiCAN vehicle profile importer.

Translates the upstream WiCAN JSON schema (used by the meatpiHQ/wican-fw
project) into our internal :class:`ProfileConfig`.

The WiCAN schema has this shape::

    {
      "car_model": "VW: e-Golf 2019 (Custom)",
      "init": "ATSP6;ATST96;",
      "pids": [
        {
          "pid": "22028C1",          # first 2 chars = mode, rest = pid hex
          "pid_init": "ATSH7E5;ATCRA7ED;",
          "parameters": [
            {"name": "SOC BMS", "expression": "B4/2.5", "unit": "%", "class": "battery"}
          ]
        }
      ]
    }

This importer is the ONLY place in the codebase that knows the WiCAN
shape. Reverse de-duplication runs here: any PID whose (mode, query)
maps to a known Mode 01 standard command is promoted to
``standard_pids`` and dropped from the custom parser.

Formula translation converts WiCAN/Torque notation to canonical
notation:

    WiCAN / Torque        canonical
    ----------------      --------------
    B3                    B(3)             single unsigned byte
    S3                    S(3)             single signed byte
    [B5:B6]               B(5, 6)          multi-byte unsigned word
    [S5:S6]               S(5, 6)          multi-byte signed word
    B3:0                  BIT(3, 0)        single bit

Note: canonical notation uses comma notation ``B(5, 6)`` rather than
WiCAN's ``[B5:B6]`` colon-slice notation, because ``5:6`` inside a
Python function call is a syntax error. The slice is unambiguous from
argument count: 1 argument = single byte, 2 arguments = multi-byte
slice.
"""

import logging
import re
from typing import Any

from obdii import commands

from .._core.elm327_parsing import as_float
from .._core.schema import CustomPid, ProfileConfig
from .._core.standard_pids import is_supported_pids_bitmap

_LOGGER = logging.getLogger(__name__)

# Matches `AT<cmd> <args>;` where cmd is letters only (SH, CRA, SP, ST, Z, ...)
# and args is anything up to the next semicolon. Args may be empty (e.g. `ATZ;`).
# Whitespace between AT and cmd, and between cmd and args, is optional.
# Note: the cmd group must be letters-only (not [A-Z0-9]+) so that
# `ATSH7E5` parses as cmd=SH arg=7E5, not cmd=SH7E5 arg=''.
_WICAN_AT_CMD_RE: re.Pattern[str] = re.compile(
    r"AT\s*([A-Z]+)\s*([^;]*);?",
    re.IGNORECASE,
)


def import_wican_profile(raw: dict[str, Any]) -> ProfileConfig:
    """Translate a WiCAN profile dict into a :class:`ProfileConfig`.

    Never raises on a single bad PID - skips it and continues, so one
    malformed entry doesn't lose the whole profile. Raises
    :class:`TypeError` only if ``raw`` is not a dict at all.
    """
    if not isinstance(raw, dict):
        raise TypeError(f"WiCAN profile must be a dict, got {type(raw).__name__}")

    car_model = raw.get("car_model", "unknown")
    standard: set[str] = set()
    custom: list[CustomPid] = []

    # Optional profile-level init (e.g. ATSP6;ATST96;) - applied to
    # every PID in the profile. We merge it into each PID's
    # `init_extra` (deduplicated) so the scheduler groups correctly.
    profile_init = (raw.get("init") or "").strip()

    for block in raw.get("pids", []):
        try:
            if not isinstance(block, dict):
                continue
            mode, query = _split_wican_command(block.get("pid", ""))
            if not mode:
                continue
            header, can_filter, extra_init = _parse_pid_init(block.get("pid_init"))
            if profile_init:
                extra_init = _merge_init_strings(profile_init, extra_init)

            # Reverse de-dup: Mode 01 PIDs with a known standard name get
            # promoted to standard_pids and dropped from custom_pids.
            std_name = _match_standard_pid(mode, query)
            if std_name:
                standard.add(std_name)
                continue

            for param in _iter_parameters(block.get("parameters")):
                formula = _translate_formula(param.get("expression", ""))
                if not formula:
                    continue
                pid_name = param.get("name") or f"{mode}{query}"
                pid_id = f"{mode}:{query}:{pid_name}"
                custom.append(
                    CustomPid(
                        id=pid_id,
                        name=pid_name,
                        mode=mode,
                        query=query,
                        formula=formula,
                        can_header=header,
                        can_filter=can_filter,
                        init_extra=extra_init,
                        unit=param.get("unit"),
                        device_class=param.get("class"),
                        state_class=param.get("state_class"),
                        min_value=as_float(param.get("min")),
                        max_value=as_float(param.get("max")),
                        source=f"import:wican:{car_model}",
                    )
                )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Skipping malformed WiCAN PID block in profile %r: %s", car_model, err
            )

    return ProfileConfig(
        standard_pids=sorted(standard),
        custom_pids=custom,
    )


class WicanImporter:
    """Protocol-conforming importer for runtime dispatch.

    Use the module-level :func:`import_wican_profile` function for
    direct calls. Use this class when you need a uniform
    :class:`ProfileImporter` interface across multiple importer types.
    """

    def can_handle(self, raw: object) -> bool:
        """Return True if ``raw`` looks like a WiCAN profile dict."""
        return isinstance(raw, dict) and ("pids" in raw or "car_model" in raw)

    def import_profile(self, raw: object) -> ProfileConfig:
        """Translate a WiCAN profile dict into a :class:`ProfileConfig`."""
        if not isinstance(raw, dict):
            raise TypeError(f"WiCAN profile must be a dict, got {type(raw).__name__}")
        return import_wican_profile(raw)


def _split_wican_command(raw: Any) -> tuple[str, str]:
    """Split a WiCAN ``pid`` field like ``'22028C1'`` into ``('22', '028C1')``.

    The first 2 chars are the mode (hex byte as text); the rest is the
    PID/DID payload. Returns ``('', '')`` if the input is too short or
    not a string.
    """
    if not isinstance(raw, str):
        return ("", "")
    s = raw.strip().upper()
    if len(s) < 3:
        return ("", "")
    return (s[:2], s[2:])


def _parse_pid_init(raw: str | None) -> tuple[str | None, str | None, str | None]:
    """Parse a WiCAN ``pid_init`` string into ``(header, filter, extra_init)``.

    Example: ``'ATSH7E5;ATCRA7ED;' -> ('7E5', '7ED', None)``.
    Anything beyond ATSH/ATCRA goes into ``extra_init`` verbatim,
    semicolon-joined, so the scheduler can group on it as a real value.
    """
    if not raw:
        return (None, None, None)
    header: str | None = None
    can_filter: str | None = None
    extras: list[str] = []
    for match in _WICAN_AT_CMD_RE.finditer(raw):
        cmd = match.group(1).upper()
        arg = (match.group(2) or "").strip()
        if cmd == "SH" and arg:
            header = arg
        elif cmd == "CRA" and arg:
            can_filter = arg
        else:
            extras.append(f"AT{cmd} {arg}".strip())
    return (header, can_filter, ";".join(extras) if extras else None)


def _merge_init_strings(a: str, b: str | None) -> str | None:
    """Merge two init strings, preserving order and dropping duplicates.

    Comparison is done on a whitespace-stripped, uppercased key so
    ``'ATSP6'`` and ``'at sp 6'`` don't both survive.
    """
    parts_a = [p.strip() for p in a.split(";") if p.strip()]
    parts_b = [p.strip() for p in (b or "").split(";") if p.strip()]
    seen: set[str] = set()
    merged: list[str] = []
    for p in parts_a + parts_b:
        key = re.sub(r"\s+", "", p).upper()
        if key in seen:
            continue
        seen.add(key)
        merged.append(p)
    return ";".join(merged) if merged else None


def _iter_parameters(raw: object) -> list[dict[str, Any]]:
    """Yield parameter dicts from a WiCAN ``parameters`` block.

    The WiCAN schema allows ``parameters`` to be either:
      - a list of dicts (modern):  ``[{"name": ..., "expression": ...}, ...]``
      - a dict of ``{name: expression}`` (Torque-style shorthand)

    Normalize to list-of-dicts. The Torque-style form loses
    unit/class/min/max (those fields don't exist in the shorthand),
    but at least the parameter name and expression survive.
    """
    if isinstance(raw, list):
        return [p for p in raw if isinstance(p, dict)]
    if isinstance(raw, dict):
        return [
            {"name": k, "expression": v} for k, v in raw.items() if isinstance(v, str)
        ]
    return []


def _match_standard_pid(mode: str, query: str) -> str | None:
    """If ``(mode, query)`` is a known Mode 01 standard PID, return its canonical name.

    The match is on address (mode + PID hex), not on formula text. If
    a manufacturer ships a remapped/rescaled version of a standard PID
    under the same address, the wire command is what determines whether
    it can be served by the native obdii Mode 01 path - so we promote
    it to ``standard_pids`` and drop the custom formula. This is the
    "Reverse De-duplication Strategy" requirement.

    Returns None for non-Mode-01 PIDs (the standard catalog only
    covers Mode 01), for unknown PIDs, and for the SUPPORTED_PIDS_A..G
    bitmaps themselves (they're metadata, not user-trackable parameters).
    """
    if mode != "01":
        return None
    # Standard Mode 01 PIDs are 2 hex chars (0x00-0xE0 in 0x20 increments).
    # Some WiCAN profiles pad the PID with extra zeros; take the first 2.
    pid_hex = query[:2]
    try:
        pid_int = int(pid_hex, 16)
    except ValueError:
        return None
    try:
        cmd = commands[1][pid_int]
    except KeyError:
        return None
    if cmd is None or cmd.name == "Unnamed":
        return None
    if is_supported_pids_bitmap(cmd.name):
        return None
    return cmd.name


def _translate_formula(expr: Any) -> str:
    """Translate WiCAN/Torque notation to canonical notation.

    See module docstring for the translation table. Order matters:
    multi-byte slices (with brackets) first, then single-bit extraction
    (with ``:``), then plain single-byte references.
    """
    if not isinstance(expr, str):
        return ""
    s = expr.strip()
    if not s:
        return ""

    # 1. Multi-byte slices: [B5:B6] or [S5:S6] (case-insensitive).
    #    Strip leading zeros from byte indices (B09 -> B(9), not B(09))
    #    because Python 3 rejects leading zeros in integer literals.
    s = re.sub(
        r"\[\s*([BS])\s*(\d+)\s*:\s*([BS])\s*(\d+)\s*\]",
        lambda m: f"{m.group(1).upper()}({int(m.group(2))}, {int(m.group(4))})",
        s,
        flags=re.IGNORECASE,
    )

    # 2. Single-bit extraction: B3:0 or S3:1 (byte 3, bit 0/1).
    #    Must come BEFORE the plain B3/S3 form so the `:0` part isn't
    #    eaten by the single-byte regex first.
    s = re.sub(
        r"\b([BS])(\d+):(\d+)\b",
        lambda m: f"BIT({int(m.group(2))}, {int(m.group(3))})",
        s,
        flags=re.IGNORECASE,
    )

    # 3. Single byte: B3 or S3 (case-insensitive)
    s = re.sub(
        r"\b([BS])(\d+)\b",
        lambda m: f"{m.group(1).upper()}({int(m.group(2))})",
        s,
        flags=re.IGNORECASE,
    )

    return s.strip()
