"""Extract ad-hoc fields from a log message via user regexes with named groups —
pure, no Qt, so it's unit-testable.

A pattern like ``latency=(?P<ms>\\d+)ms`` pulls a `ms` field out of every matching
line. Invalid patterns are skipped (never raised) so one bad entry can't break the
whole set; the first match wins per group name across the pattern list.
"""

from __future__ import annotations

import re
from re import Pattern


def compile_extractors(patterns: list[str]) -> list[Pattern]:
    """Compile each pattern, dropping any that don't compile or have no named
    groups (a pattern with no `(?P<name>…)` extracts nothing)."""
    compiled: list[Pattern] = []
    for p in patterns:
        if not p:
            continue
        try:
            rx = re.compile(p)
        except re.error:
            continue
        if rx.groupindex:  # has at least one named group
            compiled.append(rx)
    return compiled


def extract(message: str, patterns: list[Pattern]) -> dict[str, str]:
    """Return `{group_name: value}` from the first match of each pattern.

    Groups already filled by an earlier pattern are not overwritten (first match
    wins). Non-matching patterns and unmatched optional groups contribute nothing.
    """
    fields: dict[str, str] = {}
    for rx in patterns:
        m = rx.search(message)
        if not m:
            continue
        for name, value in m.groupdict().items():
            if value is not None and name not in fields:
                fields[name] = value
    return fields
