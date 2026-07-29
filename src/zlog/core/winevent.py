"""Pure parsing/mapping for Windows Event Log capture.

`win32evtlog.EvtRender(handle, EvtRenderEventXml)` returns each event as a
System-XML string (see the Microsoft Event Schema). The actual query/subscribe
plumbing is Windows-only and lives in `zlog.winlog`; everything here is
OS-free (stdlib `xml.etree` only, no pywin32, no Qt), so it's unit-testable
against fixture XML on any platform, like `core/dbwin.py`.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from zlog.core.models import LogEntry

_NS = "{http://schemas.microsoft.com/win/2004/08/events/event}"

# Windows Event Log levels (System/Level): 0 LogAlways, 1 Critical, 2 Error,
# 3 Warning, 4 Information, 5 Verbose -> logcat's V/D/I/W/E/F rank scale.
_LEVEL_MAP = {"0": "I", "1": "F", "2": "E", "3": "W", "4": "I", "5": "V"}

# TimeCreated@SystemTime is ISO-8601 UTC, e.g. "2026-07-29T10:15:23.1234567Z"
# — fractional seconds can run to 7 digits, which datetime.fromisoformat()
# can't parse, so this is matched by hand rather than round-tripped through
# datetime. No year in the output, matching logcat's own format (see
# core/dbwin.format_time) — since:/until: already compare time-of-day only.
_TIMESTAMP_RE = re.compile(
    r"^\d{4}-(?P<mo>\d{2})-(?P<d>\d{2})T"
    r"(?P<h>\d{2}):(?P<mi>\d{2}):(?P<s>\d{2})(?:\.(?P<frac>\d+))?"
)


def map_level(value: str | None) -> str:
    """Best-effort severity for a System/Level value; unrecognized or missing
    values read as Information rather than raising."""
    return _LEVEL_MAP.get(value, "I") if value else "I"


def format_event_time(system_time: str) -> str:
    """Render an EventLog `SystemTime` in logcat's `MM-DD HH:MM:SS.mmm` shape.
    Returns "" for anything that doesn't match (never raises)."""
    m = _TIMESTAMP_RE.match(system_time or "")
    if not m:
        return ""
    frac = (m.group("frac") or "0").ljust(3, "0")[:3]
    return f"{m.group('mo')}-{m.group('d')} {m.group('h')}:{m.group('mi')}:{m.group('s')}.{frac}"


def _text(parent: ET.Element | None, tag: str) -> str | None:
    if parent is None:
        return None
    child = parent.find(f"{_NS}{tag}")
    return child.text if child is not None else None


def _event_data_message(root: ET.Element, event_id: str | None) -> str:
    """Fallback message built from raw `<EventData><Data>` values — always
    available even without resolving the provider's message-table strings
    (which needs a separate, provider-specific, potentially slow Win32 call;
    left to a future pass, see docs/plans/windows-event-log.md)."""
    data = root.find(f"{_NS}EventData")
    values = [d.text for d in data.findall(f"{_NS}Data")] if data is not None else []
    message = "; ".join(v for v in values if v)
    if event_id:
        return f"[{event_id}] {message}" if message else f"Event {event_id}"
    return message


def parse_event_xml(xml_text: str) -> LogEntry:
    """Map one rendered event's System XML to a `LogEntry`. Malformed XML or a
    missing `<System>` block degrades to a raw-text entry (empty structured
    fields, the XML itself as the message) rather than raising — matching
    `core.parser.parse_line`'s fallback for an unrecognized line."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return LogEntry(time="", pid="", tid="", level="", tag="", message=xml_text)

    system = root.find(f"{_NS}System")
    if system is None:
        return LogEntry(time="", pid="", tid="", level="", tag="", message=xml_text)

    provider = system.find(f"{_NS}Provider")
    tag = (provider.get("Name") if provider is not None else None) or "EventLog"

    time_el = system.find(f"{_NS}TimeCreated")
    time_str = format_event_time(time_el.get("SystemTime", "")) if time_el is not None else ""

    exec_el = system.find(f"{_NS}Execution")
    pid = (exec_el.get("ProcessID") if exec_el is not None else None) or ""
    tid = (exec_el.get("ThreadID") if exec_el is not None else None) or ""

    event_id = _text(system, "EventID")
    message = _event_data_message(root, event_id)

    return LogEntry(
        time=time_str,
        pid=pid,
        tid=tid,
        level=map_level(_text(system, "Level")),
        tag=tag,
        message=message,
        source="evtlog",
    )
