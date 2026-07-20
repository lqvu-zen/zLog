"""A pure `LogEntry` predicate built from a `QuerySpec` — no Qt.

The GUI filters through a `QSortFilterProxyModel`; that logic can't run headless.
This mirrors the same gates as a plain callable so non-GUI consumers (the CLI
tail mode, tests) can filter entries the same way the query bar does.

Supported gates: min level / exact level set, tag-contains, PID include/exclude,
and a search + exclude text/regex over `tag + message`. Process-name (`proc:`)
and time-range (`since:`/`until:`) gates are GUI-only — they need the live PID→
name map / a running clock the CLI doesn't have — and are ignored here.
"""

from __future__ import annotations

from collections.abc import Callable

from zlog.core.models import LEVEL_RANK, LogEntry
from zlog.core.query import QuerySpec
from zlog.core.search import compile_matcher


def build_predicate(spec: QuerySpec, case: bool = False) -> Callable[[LogEntry], bool]:
    """Return `ok(entry) -> bool` applying the spec's headless-supportable gates."""
    search = compile_matcher(spec.search, spec.regex, case)
    excludes = [compile_matcher(x, False, case) for x in spec.excludes if x]
    levels = set(spec.levels)
    min_rank = LEVEL_RANK.get(spec.level, 0) if spec.level else 0
    tag_needle = spec.tag.lower()
    pids = set(spec.pids)
    exclude_pids = set(spec.exclude_pids)

    def ok(entry: LogEntry) -> bool:
        if levels:
            if entry.level not in levels:
                return False
        elif spec.level and LEVEL_RANK.get(entry.level, 0) < min_rank:
            return False
        if tag_needle and tag_needle not in entry.tag.lower():
            return False
        if pids and entry.pid not in pids:
            return False
        if exclude_pids and entry.pid in exclude_pids:
            return False
        haystack = f"{entry.tag} {entry.message}"
        if not search(haystack):
            return False
        return all(not ex(haystack) for ex in excludes)

    return ok
