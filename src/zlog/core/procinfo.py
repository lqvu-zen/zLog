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

# Glyph marking a name that's both log-seen and currently running, in the merged
# Load list (see `merge_candidates`). Matches the tab bar's live-session marker
# so "still running" reads the same way everywhere.
RUNNING_MARKER = "●"


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


def merge_candidates(log_names, running) -> list[str]:
    """Union of `log_names` (strings) and `running` (`ProcessInfo`s) for the App
    box's Load list: case-insensitively deduped and sorted, with a name that's in
    both marked `"name ●"` so it reads apart from a merely historical one. Either
    side may be empty (off Windows, `running` always is) with no special-casing.
    """
    log_by_key = {name.lower(): name for name in log_names if name}
    running_by_key = {p.name.lower(): p.name for p in running if p.name}
    merged = []
    for key in log_by_key.keys() | running_by_key.keys():
        name = log_by_key.get(key) or running_by_key[key]
        if key in log_by_key and key in running_by_key:
            name = f"{name} {RUNNING_MARKER}"
        merged.append(name)
    return sorted(merged, key=str.lower)


def strip_marker(text: str) -> str:
    """Undo the `merge_candidates` marker, so Apply/typing a marked entry (picked
    from the dropdown, or copy-pasted) still resolves to the plain name. Text
    without the marker passes through unchanged."""
    text = text.strip()
    if text.endswith(RUNNING_MARKER):
        text = text[: -len(RUNNING_MARKER)].rstrip()
    return text


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
