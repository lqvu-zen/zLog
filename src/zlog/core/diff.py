"""Diff two captures by normalized line — pure, no Qt, so it's unit-testable."""

from __future__ import annotations

import difflib


def line_key(entry) -> str:
    """A stable per-line key that ignores volatile time/pid, so the same event in
    two captures compares equal."""
    return f"{entry.level}/{entry.tag}: {entry.message}"


def diff_logs(a: list[str], b: list[str]) -> list[tuple[str, str]]:
    """Unified diff of two key lists as (op, line): " " common, "-" only in a,
    "+" only in b."""
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    out: list[tuple[str, str]] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out.extend((" ", line) for line in a[i1:i2])
        elif op == "delete":
            out.extend(("-", line) for line in a[i1:i2])
        elif op == "insert":
            out.extend(("+", line) for line in b[j1:j2])
        elif op == "replace":
            out.extend(("-", line) for line in a[i1:i2])
            out.extend(("+", line) for line in b[j1:j2])
    return out
