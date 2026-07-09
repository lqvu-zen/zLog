"""Recent-query history list — pure, no Qt, so it's testable.

Most-recent-first, de-duplicated, capped. Used by the query bar's completer.
"""

from __future__ import annotations


def push_history(items: list[str], term: str, limit: int = 20) -> list[str]:
    """Return a new history with `term` moved to the front, de-duplicated and
    capped at `limit`. Blank terms are ignored (return the list unchanged)."""
    term = term.strip()
    if not term:
        return list(items)
    out = [term] + [x for x in items if x != term]
    return out[:limit]


def normalize_history(raw, limit: int = 20) -> list[str]:
    """Coerce possibly-messy stored data into a clean list of non-empty strings."""
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip() and item not in out:
            out.append(item)
    return out[:limit]
