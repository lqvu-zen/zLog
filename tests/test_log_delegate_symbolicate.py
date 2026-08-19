"""LogItemDelegate._display_message: symbolicated when a Symbolicator is
loaded, except when match spans are present (those are positions into the
raw text — see docs/plans/crash-symbolication.md). Pure method call, no
paint needed.
"""

from __future__ import annotations

from zlog.core.models import LogEntry
from zlog.core.proguard import parse_mapping
from zlog.core.symbolicate import Symbolicator
from zlog.ui.log_delegate import LogItemDelegate

_MAPPING = "com.example.app.MainActivity -> com.example.app.a:\n    void run() -> a\n"


def _entry(message: str) -> LogEntry:
    return LogEntry(
        time="06-30 12:00:00.000", pid="1", tid="2", level="E", tag="Tag", message=message
    )


def test_no_symbolicator_returns_raw_message(qapp):
    d = LogItemDelegate()
    entry = _entry("at com.example.app.a.a(SourceFile:1)")
    assert d._display_message(entry, None) == entry.message


def test_symbolicator_applied_when_no_spans(qapp):
    d = LogItemDelegate()
    d.symbolicator = Symbolicator()
    d.symbolicator.mapping = parse_mapping(_MAPPING)
    entry = _entry("at com.example.app.a.a(SourceFile:1)")
    out = d._display_message(entry, None)
    assert "MainActivity" in out


def test_raw_message_kept_when_spans_present(qapp):
    # Spans are index positions into the raw text -- applying them to a
    # symbolicated (different-length) string would misalign highlighting.
    d = LogItemDelegate()
    d.symbolicator = Symbolicator()
    d.symbolicator.mapping = parse_mapping(_MAPPING)
    entry = _entry("at com.example.app.a.a(SourceFile:1)")
    out = d._display_message(entry, [(0, 2)])
    assert out == entry.message
