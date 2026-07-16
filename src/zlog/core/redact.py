"""Mask common secrets in log messages before sharing — pure, no Qt.

Applied only on the export/save paths (never to the live view or the master
list), so it's non-destructive: it transforms a copy of each entry. The pattern
set is deliberately conservative — better to under-mask than to eat ordinary
text — and idempotent, so running it twice is the same as once.
"""

from __future__ import annotations

import re
from dataclasses import replace

from zlog.core.models import LogEntry

# Order matters: mask the specific kinds (email, ip) before the broad token
# rule, and exclude the placeholders themselves from the token rule so a second
# pass can't re-mangle them.
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# A long, mixed-case-or-digit "secret"-looking run (bearer tokens, hex digests,
# base64-ish blobs). Requires length >= 20 and at least one letter and one digit
# so ordinary long words and pure numbers are left alone.
_TOKEN = re.compile(
    r"\b(?=[A-Za-z0-9+/_\-]*[A-Za-z])(?=[A-Za-z0-9+/_\-]*\d)[A-Za-z0-9+/_\-]{20,}\b"
)


def redact_text(s: str) -> str:
    """Replace emails, IPv4 addresses, and long token-like strings with a tag."""
    if not s:
        return s
    s = _EMAIL.sub("[email]", s)
    s = _IPV4.sub("[ip]", s)
    s = _TOKEN.sub("[token]", s)
    return s


def redact_entry(entry: LogEntry) -> LogEntry:
    """A copy of `entry` with its message redacted; other fields untouched."""
    return replace(entry, message=redact_text(entry.message))


def redact_entries(entries: list[LogEntry]) -> list[LogEntry]:
    return [redact_entry(e) for e in entries]
