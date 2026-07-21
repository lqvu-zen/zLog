"""Tests for the sticky-header anchor picker (pure, no Qt)."""

from zlog.core.anchor import pick_anchor


def test_nothing_pinned_at_top():
    assert pick_anchor(0, 5, [1, 2]) is None
    assert pick_anchor(-1, 5, [1, 2]) is None  # empty view


def test_selected_row_wins_when_above_top():
    # first visible is row 10; selection row 3 has scrolled off → pin it
    assert pick_anchor(10, 3, [1, 7]) == 3


def test_nearest_bookmark_above_when_selection_not_above():
    # selection is below the fold (or none) → nearest bookmark above the top
    assert pick_anchor(10, 20, [2, 7, 15]) == 7  # 15 is below the top, ignored
    assert pick_anchor(10, -1, [2, 7]) == 7


def test_none_when_no_anchor_above():
    assert pick_anchor(10, 20, [15, 30]) is None  # no bookmark above, selection below
    assert pick_anchor(10, -1, []) is None
