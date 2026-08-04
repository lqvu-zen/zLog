"""Serializing open tabs so they can be restored on the next launch.

Pure shaping only — the window supplies the sessions and does the file loading.
Keeping validation here means a hand-edited or truncated settings file can't
produce a broken tab: anything malformed is dropped rather than raising.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_TABS = 10  # cap what we persist; restoring dozens of logs would stall launch


@dataclass(frozen=True, slots=True)
class TabState:
    """What's worth bringing back for one tab.

    A live capture isn't restorable (there's no device or buffer to resume), so
    only a **loaded file** carries a path; a streaming tab comes back as an empty
    tab that keeps its filter. That's why `path` may be empty.
    """

    path: str = ""
    query: str = ""
    level: str = "V"
    package: str = ""
    format: str = ""  # chosen LogFormat name for this tab ("" = auto-detect/built-ins)

    @property
    def restorable(self) -> bool:
        """Worth recreating? A tab with nothing in it and no filter isn't."""
        return bool(self.path or self.query or self.package)


def tabs_to_json(states) -> list[dict]:
    """Serialize tab states, newest-relevant first, capped at `MAX_TABS`."""
    out = []
    for st in states:
        if not st.restorable:
            continue
        out.append(
            {
                "path": st.path,
                "query": st.query,
                "level": st.level,
                "package": st.package,
                "format": st.format,
            }
        )
        if len(out) >= MAX_TABS:
            break
    return out


def tabs_from_json(data) -> list[TabState]:
    """Rebuild tab states from stored JSON, skipping anything malformed.

    Every field is coerced defensively: a settings file is user-editable, and one
    bad entry must not cost the whole restore (or, worse, raise during startup).
    """
    if not isinstance(data, list):
        return []
    states: list[TabState] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        state = TabState(
            path=str(item.get("path") or ""),
            query=str(item.get("query") or ""),
            level=str(item.get("level") or "V"),
            package=str(item.get("package") or ""),
            format=str(item.get("format") or ""),
        )
        if state.restorable:
            states.append(state)
        if len(states) >= MAX_TABS:
            break
    return states
