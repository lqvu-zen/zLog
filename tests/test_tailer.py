"""Follow-decisions and line splitting. Pure: no Qt, no filesystem."""

from __future__ import annotations

from zlog.core.tailer import IDLE, READ, REWIND, TailState, next_action, split_complete_lines


def test_grew_means_read():
    assert next_action(TailState(100), TailState(150)) == READ


def test_same_size_means_idle():
    assert next_action(TailState(100), TailState(100)) == IDLE


def test_shrank_means_rewind():
    """Truncated in place — the saved offset now points past the end."""
    assert next_action(TailState(100), TailState(10)) == REWIND


def test_truncated_to_empty_means_rewind():
    assert next_action(TailState(100), TailState(0)) == REWIND


def test_identity_change_means_rewind_even_when_bigger():
    """Rotated: renamed aside and recreated. Size alone would say 'read', which
    would skip the new file's first bytes."""
    assert next_action(TailState(100, key=1), TailState(120, key=2)) == REWIND


def test_identity_change_beats_equal_size():
    """The nasty case: a fresh file that happens to be the same size."""
    assert next_action(TailState(100, key="a"), TailState(100, key="b")) == REWIND


def test_same_identity_and_growth_reads():
    assert next_action(TailState(100, key=7), TailState(200, key=7)) == READ


def test_unknown_identity_falls_back_to_size():
    """A None key means 'couldn't tell' — never invent a rotation from it."""
    assert next_action(TailState(100, key=None), TailState(150, key=2)) == READ
    assert next_action(TailState(100, key=1), TailState(150, key=None)) == READ


# --- partial-line handling -------------------------------------------------
def test_split_keeps_trailing_partial_line():
    lines, rest = split_complete_lines("a\nb\npartial")
    assert lines == ["a", "b"]
    assert rest == "partial"


def test_split_on_exact_newline_leaves_no_remainder():
    lines, rest = split_complete_lines("a\nb\n")
    assert lines == ["a", "b"]
    assert rest == ""


def test_split_empty():
    assert split_complete_lines("") == ([], "")


def test_split_single_partial_line_emits_nothing():
    assert split_complete_lines("no newline yet") == ([], "no newline yet")


def test_split_works_on_bytes():
    """The follower reads binary (text-mode tell() isn't a byte offset)."""
    lines, rest = split_complete_lines(b"a\nb\npartial")
    assert lines == [b"a", b"b"]
    assert rest == b"partial"


def test_split_empty_bytes():
    assert split_complete_lines(b"") == ([], b"")
