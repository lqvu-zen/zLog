"""Tests for `core.webhook.build_payload`. No Qt or network required."""

from __future__ import annotations

from zlog.core.models import LogEntry
from zlog.core.webhook import build_payload


def test_build_payload_fields():
    entry = LogEntry("06-30 12:00:00.000", "1234", "5678", "E", "Crash", "boom")
    assert build_payload(entry) == {
        "message": "boom",
        "tag": "Crash",
        "pid": "1234",
        "level": "E",
        "time": "06-30 12:00:00.000",
        "line": "06-30 12:00:00.000 1234-5678 Crash E boom",
    }


def test_build_payload_is_json_serializable():
    import json

    entry = LogEntry("t", "1", "2", "I", "Tag", 'has "quotes" and \\ backslash')
    json.dumps(build_payload(entry))  # must not raise
