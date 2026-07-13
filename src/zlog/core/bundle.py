"""Session bundles — serialize a capture plus its query, highlights, and bookmarks.

Pure functions only (JSON in/out); the UI gathers the pieces and applies them back.
"""

from __future__ import annotations

import json

_VERSION = 1


def make_bundle(
    log_text: str,
    query: str,
    tag_highlights: dict[str, str],
    bookmarks: list[int],
) -> str:
    """Serialize a session to a JSON string."""
    return json.dumps(
        {
            "version": _VERSION,
            "log": log_text,
            "query": query,
            "tag_highlights": tag_highlights,
            "bookmarks": bookmarks,
        },
        indent=2,
        ensure_ascii=False,
    )


def parse_bundle(text: str) -> dict:
    """Parse a session JSON string into a normalized dict.

    Tolerant of missing keys and wrong types (each falls back to an empty default)
    so an old or hand-edited file still opens; a non-JSON file raises ValueError for
    the caller to report.
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
    marks = []
    if isinstance(raw_marks, list):
        for m in raw_marks:
            if isinstance(m, int) and not isinstance(m, bool):
                marks.append(m)
    return {
        "log": log if isinstance(log, str) else "",
        "query": query if isinstance(query, str) else "",
        "tag_highlights": tags,
        "bookmarks": marks,
    }
