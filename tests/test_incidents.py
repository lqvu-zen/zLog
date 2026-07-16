"""Tests for the pure crash/ANR classifier. No Qt or display required."""

from collections import Counter

from zlog.core.incidents import classify_incident, format_incident_summary
from zlog.core.models import LogEntry


def _entry(message, level="E", tag="Tag"):
    return LogEntry("12:00:00.000", "100", "200", level, tag, message)


def test_classifies_java_crash():
    assert classify_incident(_entry("FATAL EXCEPTION: main")) == "crash"


def test_classifies_native_crash():
    assert classify_incident(_entry("Fatal signal 11 (SIGSEGV), code 1")) == "crash"


def test_classifies_anr():
    assert classify_incident(_entry("ANR in com.example.app (input)")) == "anr"


def test_ordinary_line_is_not_an_incident():
    assert classify_incident(_entry("just a regular log line", level="I")) is None


def test_format_incident_summary_empty():
    assert format_incident_summary(Counter()) == ""


def test_format_incident_summary_singular_and_plural():
    assert format_incident_summary(Counter(crash=1)) == "1 crash"
    assert format_incident_summary(Counter(crash=2, anr=1)) == "2 crashes, 1 ANR"
