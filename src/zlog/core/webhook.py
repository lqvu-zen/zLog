"""Build the JSON payload POSTed to a watch webhook — pure, no network code,
so it's unit-testable. See docs/plans/watch-webhook-notify.md.
"""

from __future__ import annotations

from zlog.core.models import LogEntry


def build_payload(entry: LogEntry) -> dict:
    """The JSON body for a watch-pattern hit.

    Same field set as `core/watch_action.py`'s `{message} {tag} {pid} {level}
    {time} {line}` command placeholders, so anyone already familiar with the
    Run-command fields recognizes this shape.
    """
    return {
        "message": entry.message,
        "tag": entry.tag,
        "pid": entry.pid,
        "level": entry.level,
        "time": entry.time,
        "line": f"{entry.time} {entry.pid}-{entry.tid} {entry.tag} {entry.level} {entry.message}",
    }
