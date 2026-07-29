"""Export a log session to CSV / JSON / HTML.

Pure functions only — no Qt, no file IO — so they're unit-testable. The UI picks a
path and writes the returned string.
"""

from __future__ import annotations

import csv
import html
import io
import json
from datetime import datetime

from zlog.core.models import LogEntry

FIELDS = ("time", "pid", "tid", "level", "tag", "message")


def _row(entry: LogEntry) -> list[str]:
    return [entry.time, entry.pid, entry.tid, entry.level, entry.tag, entry.message]


def to_csv(entries: list[LogEntry]) -> str:
    """CSV with a header row; the `csv` module quotes commas/quotes/newlines."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(FIELDS)
    for entry in entries:
        writer.writerow(_row(entry))
    return buf.getvalue()


def to_json(entries: list[LogEntry]) -> str:
    """A JSON array of objects keyed by FIELDS (pretty-printed)."""
    data = [dict(zip(FIELDS, _row(entry), strict=True)) for entry in entries]
    return json.dumps(data, indent=2, ensure_ascii=False)


def to_html(entries: list[LogEntry]) -> str:
    """A standalone, level-colored HTML table (everything escaped)."""
    head = (
        '<!DOCTYPE html>\n<html><head><meta charset="utf-8">\n'
        "<title>zLog export</title>\n<style>\n"
        "  body { font: 13px/1.4 Consolas, 'DejaVu Sans Mono', monospace; margin: 1rem; }\n"
        "  table { border-collapse: collapse; width: 100%; }\n"
        "  th, td { text-align: left; padding: 2px 8px; white-space: pre-wrap; }\n"
        "  th { border-bottom: 1px solid #999; position: sticky; top: 0; background: #fff; }\n"
        "  tr:nth-child(even) { background: #f7f7f7; }\n"
        "  .lvl-W { color: #8a6d00; } .lvl-E { color: #c62828; } .lvl-F { color: #b71c1c; }\n"
        "  .lvl-I { color: #2e7d32; } .lvl-D { color: #3b6ea5; } .lvl-V { color: #6a6a6a; }\n"
        "</style>\n</head>\n<body>\n<table>\n"
    )
    header = "<tr>" + "".join(f"<th>{html.escape(f)}</th>" for f in FIELDS) + "</tr>\n"
    body = []
    for entry in entries:
        cells = "".join(f"<td>{html.escape(v)}</td>" for v in _row(entry))
        body.append(f'<tr class="lvl-{html.escape(entry.level)}">{cells}</tr>')
    return head + header + "\n".join(body) + "\n</table>\n</body>\n</html>\n"


def to_print_html(
    entries: list[LogEntry],
    *,
    title: str = "zLog export",
    query: str = "",
    generated: str | None = None,
) -> str:
    """Print-oriented HTML for :class:`QTextDocument` -> PDF: the same level-
    colored table as `to_html`, plus a small header (title/query/line count)
    and `page-break-inside: avoid` on rows so a line never splits across pages.
    `generated` defaults to the current time; pass a fixed string in tests."""
    stamp = generated if generated is not None else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta = [f"Generated {html.escape(stamp)}", f"{len(entries)} line(s)"]
    if query:
        meta.append(f"Query: {html.escape(query)}")
    head = (
        '<!DOCTYPE html>\n<html><head><meta charset="utf-8">\n'
        f"<title>{html.escape(title)}</title>\n<style>\n"
        "  body { font: 9pt/1.3 Consolas, 'DejaVu Sans Mono', monospace; margin: 0; }\n"
        "  h1 { margin: 0 0 2px 0; font: bold 13pt sans-serif; }\n"
        "  .meta { margin: 0 0 10px 0; color: #555; font: 8pt sans-serif; }\n"
        "  table { border-collapse: collapse; width: 100%; }\n"
        "  th, td { text-align: left; padding: 1px 6px; white-space: pre-wrap; }\n"
        "  th { border-bottom: 1px solid #999; background: #fff; }\n"
        "  tr { page-break-inside: avoid; }\n"
        "  tr:nth-child(even) { background: #f7f7f7; }\n"
        "  .lvl-W { color: #8a6d00; } .lvl-E { color: #c62828; } .lvl-F { color: #b71c1c; }\n"
        "  .lvl-I { color: #2e7d32; } .lvl-D { color: #3b6ea5; } .lvl-V { color: #6a6a6a; }\n"
        "</style>\n</head>\n<body>\n"
        f"<h1>{html.escape(title)}</h1>\n"
        f"<p class='meta'>{' &middot; '.join(meta)}</p>\n"
        "<table>\n"
    )
    header = "<tr>" + "".join(f"<th>{html.escape(f)}</th>" for f in FIELDS) + "</tr>\n"
    body = []
    for entry in entries:
        cells = "".join(f"<td>{html.escape(v)}</td>" for v in _row(entry))
        body.append(f'<tr class="lvl-{html.escape(entry.level)}">{cells}</tr>')
    return head + header + "\n".join(body) + "\n</table>\n</body>\n</html>\n"


def to_markdown(entries: list[LogEntry]) -> str:
    """A GitHub-flavored Markdown table. Pipes are escaped and newlines flattened
    so a log message can't break the table."""

    def cell(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(FIELDS) + " |",
        "|" + "|".join(["---"] * len(FIELDS)) + "|",
    ]
    for entry in entries:
        lines.append("| " + " | ".join(cell(v) for v in _row(entry)) + " |")
    return "\n".join(lines) + "\n"


def to_messages(entries: list[LogEntry]) -> str:
    """Just the message text of each entry, one per line."""
    if not entries:
        return ""
    return "\n".join(entry.message for entry in entries) + "\n"
