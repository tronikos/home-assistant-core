"""CAN-context-aware query scheduling.

The scheduler groups all queryable items — standard Mode 01 commands
AND custom PIDs — by their CAN context (header, filter, extra init).
The coordinator walks the resulting plan in order, switching
ATSH/ATCRA only when the context changes between groups, INCLUDING
transitioning back to the default (header=None) context.

Why this matters (correctness, not just performance)
---------------------------------------------------
The existing coordinator runs two independent loops: standard Mode 01
commands first, custom WiCAN PIDs second. `self._current_init` is set
to the last custom PID's init string and persists across poll cycles.
If any custom PID in cycle N used a non-default header (e.g.
`ATSH7E5;ATCRA7ED;`), that's still the adapter's active receive
filter when cycle N+1 starts — and the standard-command loop runs
immediately, with no reset, against an adapter still filtering for
ECU 7ED instead of the default broadcast. Any vehicle profile that
mixes standard PIDs with header-scoped custom PIDs is at risk of
silently losing standard-PID data after the first poll.

The fix is structural: `CanContext(header=None, filter=None,
extra_init=None)` is a real, explicit value meaning "adapter default
addressing", not the absence of a value. Every queryable item carries
an explicit context. The coordinator transitions between contexts
whenever consecutive groups differ, including transitioning BACK to
the default context, so no stale header ever survives into the next
cycle's standard-PID pass.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

from .schema import CustomPid


@dataclass(frozen=True)
class CanContext:
    """A unique ELM327 addressing state.

    `header=None` is an explicit, real value meaning "adapter default
    addressing" (no ATSH issued). It is NOT the absence of a value —
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
        """Return the CAN context for this query item."""

    @property
    def key(self) -> str:
        """Return the dict key where this item's result will be stored."""

    def execute(self, connection: Any) -> Any:
        """Execute the query on the given ELM327 connection."""


@dataclass
class StandardQueryItem:
    """A standard Mode 01 PID query — uses py-obdii's Command + resolver.

    `execute()` returns the resolver's typed value verbatim — obdii
    resolvers return float (most PIDs), int (bitfields), list (O2
    sensors, supported-PID bitmaps), list-of-tuples (fuel system
    status), str (DTCs), or None. The coordinator stores whatever
    comes back; the sensor platform formats it for display.
    """

    command_name: str  # canonical obdii name, e.g. "ENGINE_SPEED"
    command: object  # obdii.Command — built by the caller
    context: CanContext = field(default_factory=CanContext)

    @property
    def key(self) -> str:
        """Return the key for storing the standard query result."""
        return self.command_name

    def execute(self, connection: Any) -> Any:
        """Execute the standard query on the given connection."""
        resp = connection.query(self.command)
        if resp is None:
            return None
        return resp.value


@dataclass
class CustomQueryItem:
    """A custom PID query — uses the compiled formula evaluator."""

    pid: CustomPid
    command: object  # obdii.Command — built from pid.mode + pid.query
    evaluator: Callable[[list[int]], float | None]
    context: CanContext

    @property
    def key(self) -> str:
        """Return the key for storing the custom query result."""
        return self.pid.name

    def execute(self, connection: Any) -> float | None:
        """Execute the custom query on the given connection."""
        resp = connection.query(self.command)
        if resp is None:
            return None
        # obdii.Response.unparsed is the post-reassembly payload as
        # list[int], with mode/PID bytes stripped. This is what the
        # formula evaluator expects.
        unparsed = getattr(resp, "unparsed", None)
        if not unparsed:
            return None
        return self.evaluator(list(unparsed))


def build_query_plan(
    items: Iterable[QueryItem],
) -> list[tuple[CanContext, list[QueryItem]]]:
    """Group items by CAN context, ordered with the default context first.

    The default context (`CanContext()` — all fields None) is always
    the first group, because:
      1. It's the cheapest (no ATSH/ATCRA setup needed).
      2. Standard Mode 01 PIDs always live here.
      3. Starting here matches the adapter's power-on state, so the
         coordinator can skip an unnecessary "transition to default"
         step at the top of each poll cycle.
    Other groups are sorted by (header, filter, extra_init) for
    deterministic ordering across runs.

    Within each group, items preserve their input order — callers that
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
