"""Filter presets — pure, no Qt, so it's unit-testable.

A preset is a plain JSON-able dict capturing the filter widgets' state under a
name: min level, search text, regex/case flags, and package. The UI applies one
by driving those widgets (which push through the proxy), so there's a single
filtering code path.
"""

from __future__ import annotations


def make_preset(
    name: str,
    *,
    min_level: str = "V",
    search: str = "",
    regex: bool = False,
    case: bool = False,
    package: str = "",
) -> dict:
    """Build a normalized preset dict with coerced field types."""
    return {
        "name": str(name),
        "min_level": str(min_level),
        "search": str(search),
        "regex": bool(regex),
        "case": bool(case),
        "package": str(package),
    }


def normalize_presets(raw) -> list[dict]:
    """Return a clean preset list from possibly-messy stored data: drop anything
    that isn't a dict with a non-empty name; coerce each field to its default."""
    out: list[dict] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        out.append(
            make_preset(
                name,
                min_level=item.get("min_level", "V"),
                search=item.get("search", ""),
                regex=item.get("regex", False),
                case=item.get("case", False),
                package=item.get("package", ""),
            )
        )
    return out


def upsert_preset(presets: list[dict], preset: dict) -> list[dict]:
    """Add or replace (by name, case-insensitive) and return a new list sorted by name."""
    key = preset["name"].lower()
    others = [p for p in presets if p["name"].lower() != key]
    return sorted([*others, preset], key=lambda p: p["name"].lower())


def remove_preset(presets: list[dict], name: str) -> list[dict]:
    """Return a new list without the preset of this name (case-insensitive)."""
    key = name.lower()
    return [p for p in presets if p["name"].lower() != key]
