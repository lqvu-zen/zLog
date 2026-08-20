"""Tests for `core.containers.parse_containers`. No Qt or subprocess required."""

from __future__ import annotations

from zlog.core.containers import Container, parse_containers


def test_parses_several_containers():
    output = "abc123\tweb\tUp 5 minutes\ndef456\tdb\tUp 2 hours\n"
    containers = parse_containers(output)
    assert containers == [
        Container("abc123", "web", "Up 5 minutes"),
        Container("def456", "db", "Up 2 hours"),
    ]


def test_empty_output_is_empty_list():
    assert parse_containers("") == []
    assert parse_containers("\n\n") == []


def test_malformed_line_is_skipped_not_raised():
    # A line missing a field (e.g. truncated/corrupted output) is dropped
    # rather than crashing the picker — same tolerance as parse_devices.
    output = "abc123\tweb\tUp 5 minutes\nbroken-line-no-tabs\ndef456\tdb\tUp 2 hours\n"
    containers = parse_containers(output)
    assert len(containers) == 2
    assert containers[0].name == "web"
    assert containers[1].name == "db"
