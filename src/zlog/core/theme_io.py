"""Serialize a `Theme` to/from a plain dict for settings storage.

Pure and defensive: `theme_from_dict` validates every field independently and
falls back to `base`'s value for anything missing or not a valid hex color, so
a hand-edited or corrupted settings file can never produce a broken (blank or
unreadable) UI — at worst a field silently reverts to the base theme's color.
"""

from __future__ import annotations

import re
from dataclasses import asdict, fields

from zlog.core.theme import Theme

HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

_DICT_FIELDS = ("level_colors", "level_text")


def is_valid_hex(value: object) -> bool:
    return isinstance(value, str) and bool(HEX_RE.match(value))


def theme_to_dict(theme: Theme) -> dict:
    """A plain, JSON-serializable dict of every field (including the two
    per-level color dicts)."""
    return asdict(theme)


def theme_from_dict(data: object, base: Theme) -> Theme:
    """Build a `Theme` from `data`, falling back per-field to `base` for
    anything missing, the wrong type, or not a valid hex color."""
    data = data if isinstance(data, dict) else {}
    values: dict[str, object] = {}
    for f in fields(Theme):
        if f.name == "name":
            name = data.get("name")
            values["name"] = name if isinstance(name, str) and name.strip() else base.name
        elif f.name in _DICT_FIELDS:
            base_dict = getattr(base, f.name)
            raw = data.get(f.name)
            raw = raw if isinstance(raw, dict) else {}
            values[f.name] = {
                key: raw[key] if is_valid_hex(raw.get(key)) else base_dict[key] for key in base_dict
            }
        else:
            value = data.get(f.name)
            values[f.name] = value if is_valid_hex(value) else getattr(base, f.name)
    return Theme(**values)
