"""Load/save user settings as JSON — pure, no Qt, so it's unit-testable.

The UI decides *where* the file lives (an OS config dir) and how to apply the
values to widgets; this module only serializes a plain dict and is tolerant of a
missing or corrupt file (falling back to defaults).
"""

from __future__ import annotations

import copy
import json
import os

DEFAULTS: dict = {
    "geometry": "",  # base64 of QWidget.saveGeometry(), opaque to core
    "theme": "Light",
    "follow": True,
    "min_level": "V",
    "regex": False,
    "tag_highlights": {},  # tag -> hex color
    "show_details": True,
    "hidden_columns": [],
    "clear_on_start": False,
}


def load_settings(path: str) -> dict:
    """Return settings merged over defaults; unknown/missing keys are ignored.

    A missing file (OSError) or corrupt JSON (ValueError) both fall back to
    defaults. Split into two `except` clauses on purpose — the installed ruff
    formatter mangles a parenthesized `except (OSError, ValueError)` tuple.
    """
    data = copy.deepcopy(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as fh:
            stored = json.load(fh)
    except OSError:
        return data
    except ValueError:
        return data
    if isinstance(stored, dict):
        for key in DEFAULTS:
            if key in stored:
                data[key] = stored[key]
    return data


def save_settings(path: str, data: dict) -> None:
    """Write the known settings keys to `path` as JSON (creates parent dirs)."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    payload = {key: data[key] for key in DEFAULTS if key in data}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
