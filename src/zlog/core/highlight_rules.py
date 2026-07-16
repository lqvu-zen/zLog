"""Persistent highlight rules — pure, no Qt, so it's unit-testable.

A rule is a plain JSON-able dict: a pattern (substring or regex) and the color
to tint a matching row. Unlike the transient search/highlight-mode matcher,
rules apply regardless of what's currently in the search box, and persist
across restarts (see settings.py's "highlight_rules" key). Mirrors the shape of
core/presets.py.
"""

from __future__ import annotations

_DEFAULT_COLOR = "#ffeb3b"


def make_rule(pattern: str, *, regex: bool = False, color: str = _DEFAULT_COLOR) -> dict:
    """Build a normalized rule dict with coerced field types."""
    return {
        "pattern": str(pattern),
        "regex": bool(regex),
        "color": str(color) if color else _DEFAULT_COLOR,
    }


def normalize_rules(raw) -> list[dict]:
    """Return a clean rule list from possibly-messy stored data: drop anything
    that isn't a dict with a non-empty pattern; coerce each field to its
    default."""
    out: list[dict] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        pattern = item.get("pattern")
        if not isinstance(pattern, str) or not pattern.strip():
            continue
        out.append(
            make_rule(
                pattern,
                regex=item.get("regex", False),
                color=item.get("color", _DEFAULT_COLOR),
            )
        )
    return out
