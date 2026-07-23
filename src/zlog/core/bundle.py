"""Session bundles — serialize a capture plus its query, highlights, and bookmarks.

Pure functions only (JSON in/out); the UI gathers the pieces and applies them back.
"""

from __future__ import annotations

import json

_VERSION = 2  # v2 stores bookmarks as {row: label}; v1's list[int] still parses


def make_bundle(
    log_text: str,
    query: str,
    tag_highlights: dict[str, str],
    bookmarks: dict[int, str],
) -> str:
    """Serialize a session to a JSON string. `bookmarks` maps source-row -> label
    ("" for unlabeled)."""
    return json.dumps(
        {
            "version": _VERSION,
            "log": log_text,
            "query": query,
            "tag_highlights": tag_highlights,
            "bookmarks": {str(row): label for row, label in bookmarks.items()},
        },
        indent=2,
        ensure_ascii=False,
    )


def parse_bundle(text: str) -> dict:
    """Parse a session JSON string into a normalized dict.

    Tolerant of missing keys and wrong types (each falls back to an empty default)
    so an old or hand-edited file still opens; a non-JSON file raises ValueError for
    the caller to report. `bookmarks` is always returned as a {row: label} dict,
    reading either the v2 mapping or a v1 `list[int]` (labels become "").
    """
    data = json.loads(text)
    if not isinstance(data, dict):
        data = {}
    log = data.get("log")
    query = data.get("query")
    raw_tags = data.get("tag_highlights")
    raw_marks = data.get("bookmarks")
    tags = {}
    if isinstance(raw_tags, dict):
        tags = {str(k): str(v) for k, v in raw_tags.items()}
    marks: dict[int, str] = {}
    if isinstance(raw_marks, dict):  # v2: {row: label}
        for k, v in raw_marks.items():
            # Split into two except clauses on purpose — the installed ruff
            # formatter mangles a parenthesized `except (TypeError, ValueError)`.
            try:
                marks[int(k)] = str(v)
            except TypeError:
                continue
            except ValueError:
                continue
    elif isinstance(raw_marks, list):  # v1: [row, ...]
        for m in raw_marks:
            if isinstance(m, int) and not isinstance(m, bool):
                marks[m] = ""
    return {
        "log": log if isinstance(log, str) else "",
        "query": query if isinstance(query, str) else "",
        "tag_highlights": tags,
        "bookmarks": marks,
    }
