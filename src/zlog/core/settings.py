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
    "case": False,  # case-sensitive search
    "tag_highlights": {},  # tag -> hex color
    "show_details": True,
    "hidden_columns": [],
    "clear_on_start": False,
    "last_device": "",  # serial of the last-selected device, reselected on launch
    "filter_presets": [],  # named filter combos (see core/presets.py)
    "search_mode": "filter",  # "filter" hides non-matches; "highlight" tints matches
    "time_mode": "absolute",  # Time column: "absolute" | "since_start" | "delta"
    "font_delta": 0,  # point-size offset applied to the table + detail pane
    "search_history": [],  # recent query-bar entries (see core/history.py)
    "log_buffers": [],  # adb logcat -b buffers ([] = adb default)
    "tail_count": 0,  # start from the last N lines (0 = whole buffer)
    "max_rows": 0,  # ring-buffer cap on retained lines (0 = unlimited)
    "recent_files": [],  # recently opened/saved .log paths (see core/history.py)
    "reopen_last": False,  # reopen the most-recent log on launch
    "autosave": False,  # stream capture to disk while running (see core/autosave.py)
    "splitter_state": "",  # base64 QSplitter.saveState() for the log/detail divider
    "collapse": False,  # hide consecutive duplicate lines
    "watch": "",  # substring; notify when a captured line matches
    "show_process": False,  # show the resolved process/package-name column
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
