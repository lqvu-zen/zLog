"""Run one query against every open tab's full row list — see
docs/plans/cross-tab-search.md.

Deliberately thin: the actual filtering logic is `core.logfilter.build_predicate`,
already built (for the CLI's headless tail mode) to turn a `QuerySpec` into a
plain `LogEntry -> bool` predicate without a `QSortFilterProxyModel`. This module
only applies it across several sessions and keeps track of which tab each match
came from.
"""

from __future__ import annotations

from dataclasses import dataclass

from zlog.core.logfilter import build_predicate
from zlog.core.models import LogEntry
from zlog.core.query import QuerySpec

# Gates core/logfilter.py's build_predicate silently ignores (see its docstring):
# it has no live PID->name map or clock, so proc:/since:/until: never filter here.
# Surfacing this in the dialog beats a silent behavior difference from a same-tab
# query-bar search using the identical text.
_UNSUPPORTED_HINT = (
    "proc:/since:/until: aren't supported in Search All Tabs (see core/logfilter.py) "
    "and are ignored below."
)


@dataclass(frozen=True, slots=True)
class TabMatch:
    session_index: int
    source_row: int
    entry: LogEntry


def unsupported_gates(spec: QuerySpec) -> bool:
    """True if `spec` uses a gate `build_predicate` can't apply headlessly."""
    return bool(spec.process or spec.exclude_process or spec.since or spec.until)


def search_sessions(sessions, spec: QuerySpec, case: bool = False) -> list[TabMatch]:
    """Search every session's full row list with `spec`, in tab order.

    `sessions` is any sequence of objects with a `.model` exposing
    `all_entries() -> list[LogEntry]` (a real `LogSession` in the app; a bare stub
    in tests). Matches are grouped by tab via `session_index` (position in
    `sessions`), not by identity, so the caller can map straight back to its own
    tab bar.
    """
    predicate = build_predicate(spec, case)
    matches: list[TabMatch] = []
    for session_index, sess in enumerate(sessions):
        for source_row, entry in enumerate(sess.model.all_entries()):
            if predicate(entry):
                matches.append(TabMatch(session_index, source_row, entry))
    return matches
