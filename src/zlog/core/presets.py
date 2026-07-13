"""Filter presets — pure, no Qt, so it's unit-testable.

A preset is a plain JSON-able dict capturing the filter state under a name. The
`query` field holds the raw query-bar text and is the source of truth when
applying a preset (it preserves tag:/-exclude/multi-level tokens that the
decomposed search/regex/package fields cannot). The older fields are kept for
backward compatibility and for the human-readable summary.
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
    query: str = "",
) -> dict:
    """Build a normalized preset dict with coerced field types."""
    return {
        "name": str(name),
        "min_level": str(min_level),
        "search": str(search),
        "regex": bool(regex),
        "case": bool(case),
        "package": str(package),
        "query": str(query),
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
                query=item.get("query", ""),
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


def preset_summary(preset: dict) -> str:
    """A short human-readable summary of a preset's filter (for tooltips/preview)."""
    parts = []
    level = preset.get("min_level", "V")
    if level and level != "V":
        parts.append(f"level:{level}")
    query = preset.get("query", "")
    if query:
        # The raw query already encodes tag:/-exclude/regex/package tokens.
        parts.append(query)
    else:
        package = preset.get("package", "")
        if package:
            parts.append(f"package:{package}")
        search = preset.get("search", "")
        if search:
            parts.append(f"/{search}/" if preset.get("regex") else search)
    if preset.get("case"):
        parts.append("(case-sensitive)")
    return " ".join(parts) or "(show everything)"
