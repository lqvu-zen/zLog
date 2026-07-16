"""Tests for export-time secret redaction — pure, no Qt."""

from zlog.core.models import LogEntry
from zlog.core.redact import redact_entries, redact_entry, redact_text


def test_masks_email():
    assert redact_text("login from user.name+tag@example.co.uk ok") == "login from [email] ok"


def test_masks_ipv4_even_with_port():
    assert redact_text("connect 192.168.1.10:8080") == "connect [ip]:8080"


def test_masks_long_token():
    tok = "ghp_AbCd1234EfGh5678IjKl90"  # 26 chars, mixed letters+digits
    assert redact_text(f"Authorization: Bearer {tok}") == "Authorization: Bearer [token]"


def test_leaves_ordinary_text_and_short_numbers_alone():
    s = "ActivityManager: Start proc pid 1287 for com.example.app"
    assert redact_text(s) == s


def test_leaves_long_pure_words_and_numbers_alone():
    # No digit -> not a token; pure digits -> not a token.
    assert redact_text("ThisIsAVeryLongCamelCaseIdentifier") == "ThisIsAVeryLongCamelCaseIdentifier"
    assert redact_text("12345678901234567890") == "12345678901234567890"


def test_idempotent():
    s = "mail a@b.com ip 10.0.0.1 tok ghp_AbCd1234EfGh5678IjKl90"
    once = redact_text(s)
    assert redact_text(once) == once


def test_redact_entry_only_touches_message_and_copies():
    e = LogEntry("06-30 12:00:00.000", "1287", "1287", "I", "Net", "to a@b.com")
    r = redact_entry(e)
    assert r.message == "to [email]"
    assert (r.time, r.pid, r.tid, r.level, r.tag) == (e.time, e.pid, e.tid, e.level, e.tag)
    assert e.message == "to a@b.com"  # original unchanged (frozen copy)


def test_redact_entries_maps_all():
    es = [
        LogEntry("t", "1", "2", "I", "T", "a@b.com"),
        LogEntry("t", "1", "2", "I", "T", "nothing here"),
    ]
    out = redact_entries(es)
    assert [e.message for e in out] == ["[email]", "nothing here"]
