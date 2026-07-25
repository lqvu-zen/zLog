"""Running-process shaping for the "focus one app" picker.

Pure and OS-free: enumerating processes is Windows-specific and lives in
`zlog.winlog.processes`, but sorting, searching, and rewriting the query to focus
a chosen app are plain data transforms, so they unit-test on any platform.
"""

from __future__ import annotations

from dataclasses import dataclass

from zlog.core.query import remove_span, token_spans

# Query token kinds this module replaces when focusing on an app. Dropping both
# means switching targets never leaves a stale filter behind that would AND with
# the new one and hide everything.
_FOCUS_KINDS = ("proc", "package", "pid")


@dataclass(frozen=True, slots=True)
class ProcessInfo:
    """One running process as the picker shows it."""

    pid: int
    name: str  # image name, e.g. "myapp.exe"

    @property
    def label(self) -> str:
        return f"{self.name} ({self.pid})"


def sort_processes(procs) -> list[ProcessInfo]:
    """Case-insensitive by name, then pid — a stable order for the picker list."""
    return sorted(procs, key=lambda p: (p.name.lower(), p.pid))


def filter_processes(procs, needle: str) -> list[ProcessInfo]:
    """Type-to-search: match the name (case-insensitively) or the pid as typed.
    An empty needle returns everything."""
    text = needle.strip().lower()
    if not text:
        return list(procs)
    return [p for p in procs if text in p.name.lower() or text in str(p.pid)]


def focus_query(query: str, *, name: str | None = None, pid: int | None = None) -> str:
    """Return `query` refocused on one app.

    Existing `proc:`/`package:`/`pid:` tokens are stripped (by span, so quoted
    values and duplicates are handled) and the new target is appended, leaving
    every other token — level, tag, excludes, regex — untouched. Passing neither
    `name` nor `pid` just clears the focus.
    """
    text = query
    # Right-to-left so earlier spans stay valid as we slice.
    for start, end, kind in reversed(token_spans(text)):
        if kind in _FOCUS_KINDS:
            text = remove_span(text, start, end)
    parts = text.split()
    if pid is not None:
        parts.append(f"pid:{pid}")
    elif name:
        parts.append(f'proc:"{name}"' if " " in name else f"proc:{name}")
    return " ".join(parts)
