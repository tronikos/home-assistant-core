"""CAN-context-aware query scheduling.

Groups all queryable items (standard Mode 01 commands AND custom PIDs)
by their CAN context (header, filter, extra init). The coordinator
walks the resulting plan in order, switching ATSH/ATCRA only when the
context changes between groups - including transitioning back to the
default (header=None) context.

`CanContext(header=None, filter=None, extra_init=None)` is a real,
explicit value meaning "adapter default addressing", not the absence
of a value. Treating it as a first-class context ensures no stale
header from a custom PID survives into the next cycle's standard-PID
pass.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

from .helpers import extract_dirty_array
from .schema import CustomPid


@dataclass(frozen=True)
class CanContext:
    """A unique ELM327 addressing state.

    `header=None` is an explicit, real value meaning "adapter default
    addressing" (no ATSH issued). It is NOT the absence of a value -
    the scheduler treats it as a context the coordinator must actively
    transition back to.

    Frozen so it can be used as a dict key for grouping.
    """

    header: str | None = None
    filter: str | None = None
    extra_init: str | None = None


class QueryItem(Protocol):
    """A single queryable item, regardless of whether it's standard or custom.

    The coordinator doesn't care about the difference at schedule time;
    it only needs to know which context the item belongs to, what dict
    key to write the value to, and how to execute the query.
    """

    @property
    def context(self) -> CanContext:
        """Return the CAN context this item belongs to."""

    @property
    def key(self) -> str:
        """Return the dict key the coordinator stores the value under."""

    def execute(self, connection: Any) -> Any:
        """Execute the query and return the computed value, or None."""


@dataclass
class StandardQueryItem:
    """A standard Mode 01 PID query - uses py-obdii's Command + resolver.

    `execute()` returns the resolver's typed value verbatim - obdii
    resolvers return float (most PIDs), int (bitfields), list (O2
    sensors, supported-PID bitmaps), list-of-tuples (fuel system
    status), str (DTCs), or None. The coordinator stores whatever
    comes back; the sensor platform formats it for display.
    """

    command_name: str  # canonical obdii name, e.g. "ENGINE_SPEED"
    command: Any  # obdii.Command - built by the caller
    context: CanContext = field(default_factory=CanContext)

    @property
    def key(self) -> str:
        """Return the canonical obdii command name."""
        return self.command_name

    def execute(self, connection: Any) -> Any:
        """Query the standard PID and return the resolver's typed value."""
        resp = connection.query(self.command)
        if resp is None:
            return None
        # Skip BUFFER FULL responses - the ELM327's internal buffer
        # overflowed (common with fast multi-PID polling). Returning
        # None here marks the sensor unavailable for this cycle without
        # crashing the whole polling loop.
        raw = getattr(resp, "raw", None)
        if raw and b"BUFFER FULL" in raw:
            return None
        return resp.value


@dataclass
class CustomQueryItem:
    """A custom PID query - uses the compiled formula evaluator.

    Uses `extract_dirty_array(resp.raw)` rather than `resp.unparsed`
    because custom PID formulas are authored against the ELM327's raw
    text output (the "dirty array" that includes PCI bytes, mode
    echoes, and PID echoes). py-obdii's `unparsed` strips those bytes,
    which would make every formula's byte indices wrong. See
    `uops/helpers.py` for the full rationale.
    """

    pid: CustomPid
    command: Any  # obdii.Command - built from pid.mode + pid.query
    evaluator: Callable[[list[int]], float | None]
    context: CanContext

    @property
    def key(self) -> str:
        """Return the custom PID's display name."""
        return self.pid.name

    def execute(self, connection: Any) -> float | None:
        """Query the custom PID, build the dirty array, evaluate the formula."""
        resp = connection.query(self.command)
        if resp is None:
            return None
        raw = getattr(resp, "raw", None)
        if not raw:
            return None
        # Skip BUFFER FULL responses - the ELM327's internal buffer
        # overflowed (common with fast multi-PID polling).
        if b"BUFFER FULL" in raw:
            return None
        # Build the dirty array from the raw ELM327 text response.
        # This is the data contract custom formulas are written against.
        dirty_array = extract_dirty_array(raw)
        if not dirty_array:
            return None
        return self.evaluator(dirty_array)


def build_query_plan(
    items: Iterable[QueryItem],
) -> list[tuple[CanContext, list[QueryItem]]]:
    """Group items by CAN context, ordered with the default context first.

    The default context (`CanContext()` - all fields None) is always
    the first group, because:
      1. It's the cheapest (no ATSH/ATCRA setup needed).
      2. Standard Mode 01 PIDs always live here.
      3. Starting here matches the adapter's power-on state, so the
         coordinator can skip an unnecessary "transition to default"
         step at the top of each poll cycle.
    Other groups are sorted by (header, filter, extra_init) for
    deterministic ordering across runs.

    Within each group, items preserve their input order - callers that
    care about intra-group ordering (e.g. "fast-changing PIDs first")
    should pre-sort their input.
    """
    groups: dict[CanContext, list[QueryItem]] = defaultdict(list)
    for item in items:
        groups[item.context].append(item)

    default = CanContext()
    ordered: list[tuple[CanContext, list[QueryItem]]] = []
    if default in groups:
        ordered.append((default, groups.pop(default)))
    ordered.extend(
        (ctx, groups[ctx])
        for ctx in sorted(
            groups,
            key=lambda c: (c.header or "", c.filter or "", c.extra_init or ""),
        )
    )
    return ordered


def context_for_custom_pid(pid: CustomPid) -> CanContext:
    """Derive the CAN context for a custom PID from its schema fields."""
    return CanContext(
        header=pid.can_header,
        filter=pid.can_filter,
        extra_init=pid.init_extra,
    )
