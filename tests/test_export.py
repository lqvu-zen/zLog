"""Tests for the pure export formatters. No Qt or display required."""

import csv
import io
import json

from zlog.core.export import FIELDS, to_csv, to_html, to_json
from zlog.core.models import LogEntry


def _entries():
    return [
        LogEntry("06-30 12:00:00.000", "1", "2", "I", "Tag", "hello, world"),
        LogEntry("06-30 12:00:01.000", "1", "2", "E", "Crash", "<boom> & fail"),
    ]


def test_csv_has_header_and_rows_and_escapes():
    rows = list(csv.reader(io.StringIO(to_csv(_entries()))))
    assert rows[0] == list(FIELDS)
    assert len(rows) == 3  # header + 2
    assert rows[1][5] == "hello, world"  # comma survived quoting


def test_json_roundtrips_to_dicts():
    data = json.loads(to_json(_entries()))
    assert isinstance(data, list) and len(data) == 2
    assert set(data[0]) == set(FIELDS)
    assert data[1]["level"] == "E" and data[1]["message"] == "<boom> & fail"


def test_html_escapes_and_is_a_document():
    out = to_html(_entries())
    assert out.startswith("<!DOCTYPE html>")
    assert "&lt;boom&gt; &amp; fail" in out  # escaped, can't break the page
    assert 'class="lvl-E"' in out
    assert "<boom>" not in out  # raw angle brackets never leak


def test_empty_exports_are_valid():
    assert to_csv([]).strip() == ",".join(FIELDS)  # header only
    assert json.loads(to_json([])) == []
    assert "<table>" in to_html([])
