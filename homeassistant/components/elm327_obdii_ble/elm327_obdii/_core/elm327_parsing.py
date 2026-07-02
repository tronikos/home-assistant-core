"""ELM327 raw-response parsing and small coercion helpers.

The "dirty array" data contract
-------------------------------
Custom OBD-II formulas in WiCAN, Torque, and RealDash profiles are
written by users looking at raw ELM327 terminal output. When a user
sends ``22 028C`` and sees::

    7E8 05 62 02 8C 1F A0 03 E8

...they count bytes from left to right starting at the PCI byte:
index 0 = ``05`` (PCI), 1 = ``62`` (mode echo), 2 = ``02`` (PID high),
3 = ``8C`` (PID low), 4 = ``1F`` (first payload byte), etc. A formula
like ``B(4) / 2.55`` refers to that 5th byte overall.

This is the de facto industry-standard data contract for custom PID
formulas. py-obdii's ``Response.unparsed`` is a *clean* payload with
PCI/mode/PID bytes stripped - which is correct for standard Mode 01
PIDs (where py-obdii's own typed resolvers handle the scaling), but
*wrong* for custom PIDs whose formulas were authored against the
dirty-array convention.

ELM327 adapters with ``AT CAF1`` (CAN Auto Formatting, the default)
handle ISO 15765-2 multi-frame reassembly in hardware and emit the
reassembled payload as a single text response. The interspersed PCI
bytes that appear at frame boundaries in the dirty array are the
*adapter's* PCI bytes, not raw CAN-frame PCI bytes - they're part
of the ELM327's text output format that formula authors see and
count against.
"""

import logging
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)

_OBD_ERROR_TOKENS = ("DATA", "ERROR", "STOPPED", "UNABLE", "BUS")

_HEX_RE = re.compile(r"^[0-9A-Fa-f]+$")

# Matches 1-2 digits, decimal point, 1-3 digits (e.g. "14.2V", "12.80V",
# "14.234V"). Negative lookarounds prevent matching longer numbers like
# "123.45".
_VOLTAGE_RE = re.compile(r"(?<!\d)(\d{1,2}\.\d{1,3})(?!\d)")


def extract_dirty_array(raw_response: bytes) -> list[int]:
    """Parse an ELM327 raw text response into a flat list of hex bytes.

    This is the "dirty array" that custom PID formulas (WiCAN, Torque,
    RealDash notation) are written against. It includes PCI bytes,
    mode echoes, and PID echoes at the positions the formula authors
    see when looking at raw ELM327 terminal output.

    Handles:
      - Space-delimited packets (AT S1, default): "7E8 05 41 0C 1A F8"
      - Contiguous hex strings (AT S0, spaces off): "7E805410C1AF8"
      - 11-bit CAN headers (3 hex chars): "7E8"
      - 29-bit CAN headers (8 hex chars): "18DAF110"
      - Multi-line responses (one CAN frame per line)
      - ``>`` prompt character stripping
      - Error token filtering (DATA, ERROR, STOPPED, UNABLE, BUS)

    The CAN header token at the start of each line is skipped - only
    the data bytes (PCI + mode echo + PID echo + payload) are included
    in the returned array.
    """
    dirty_array: list[int] = []
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

            # Fallback for AT S0 (spaces off) returning contiguous hex strings.
            # A single token longer than 3 chars is a contiguous hex frame -
            # we need to split off the CAN header (3 or 8 chars) and then
            # chunk the rest into byte pairs.
            #
            # Header-length heuristic: 29-bit CAN (ISO 15765-4 / J1939)
            # headers are 8 hex chars and start with "18" (e.g. "18DAF110").
            # 11-bit CAN headers are 3 hex chars (e.g. "7E8"). Checking the
            # "18" prefix is the standard way to distinguish them in
            # spaces-off mode.
            #
            # Note: using >= 8 instead of > 8 so header-only frames (exactly
            # 8 chars, no payload) are still recognized as 29-bit and dropped
            # (no payload bytes to parse) rather than mis-parsed as 11-bit.
            if len(parts) == 1 and len(line) > 3:
                token = parts[0]
                if len(token) >= 8 and token[:2].upper() == "18":
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
                # First word is the CAN header (e.g., '7E8'). Skip it -
                # the dirty array is data bytes only (PCI + echoes + payload).
                for part in parts[1:]:
                    try:
                        dirty_array.append(int(part, 16))
                    except ValueError:
                        _LOGGER.debug("Non-hex token in frame, skipping: %r", part)

    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Could not extract dirty array: %s", err)
    return dirty_array


def extract_voltage(raw_response: bytes) -> float | None:
    """Parse a voltage float from an ``AT RV`` raw response."""
    raw_text = raw_response.decode("utf-8", errors="ignore")
    match = _VOLTAGE_RE.search(raw_text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def is_hex(s: str) -> bool:
    """True if ``s`` is a non-empty string of hex digits (no ``0x`` prefix)."""
    if not s:
        return False
    return _HEX_RE.fullmatch(s) is not None


def as_float(v: Any) -> float | None:
    """Coerce ``v`` to float, returning None on failure or empty input."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except TypeError, ValueError:
        return None
