"""Tab-label composition. Pure: no Qt, no window."""

from __future__ import annotations

from zlog.core.tabtitle import (
    DISCONNECTED,
    IDLE,
    PAUSED,
    STREAMING,
    format_count,
    tab_label,
    tab_tooltip,
)


# --- counts ----------------------------------------------------------------
def test_small_counts_are_exact():
    assert format_count(0) == "0"
    assert format_count(999) == "999"


def test_thousands_are_compact():
    assert format_count(1000) == "1.0k"
    assert format_count(1234) == "1.2k"
    assert format_count(15_000) == "15k"  # drops the decimal once it's wide


def test_millions_are_compact():
    assert format_count(1_200_000) == "1.2M"
    assert format_count(15_000_000) == "15M"


# --- labels ----------------------------------------------------------------
def test_idle_tab_is_just_the_name():
    assert tab_label("emulator-5554") == "emulator-5554"


def test_zero_count_is_omitted():
    """A fresh tab shouldn't advertise '(0)'."""
    assert tab_label("Device", IDLE, 0) == "Device"


def test_streaming_marker_and_count():
    assert tab_label("emulator-5554", STREAMING, 1234) == "● emulator-5554 (1.2k)"


def test_paused_marker():
    assert tab_label("dev", PAUSED, 340) == "⏸ dev (340)"


def test_disconnected_marker():
    assert tab_label("dev", DISCONNECTED) == "⚠ dev"


def test_long_name_is_elided_but_marker_and_count_survive():
    out = tab_label("a-very-long-capture-file-name.log", STREAMING, 12_000)
    assert out.startswith("● ")
    assert out.endswith("(12k)")  # the count is never squeezed out
    assert "…" in out


def test_empty_name_falls_back():
    assert tab_label("") == "Device"


def test_unknown_state_has_no_marker():
    assert tab_label("dev", "nonsense", 5) == "dev (5)"


# --- tooltips --------------------------------------------------------------
def test_tooltip_spells_out_state_and_exact_count():
    assert tab_tooltip("dev", STREAMING, 1234) == "dev — streaming — 1,234 lines"


def test_tooltip_is_not_elided():
    name = "a-very-long-capture-file-name.log"
    assert name in tab_tooltip(name, IDLE, 0)


def test_tooltip_idle_with_no_lines_is_just_the_name():
    assert tab_tooltip("dev") == "dev"


def test_tooltip_singular_line():
    assert tab_tooltip("a.log", IDLE, 1).endswith("1 line")
