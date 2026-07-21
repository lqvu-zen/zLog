"""Pick which row a sticky header should pin — pure, no Qt, so it's unit-testable.

All indices are view (proxy) rows. The anchor is the row you're "working on" that
has scrolled above the viewport: the selected row if it's off the top, else the
nearest bookmark above the top, else nothing.
"""

from __future__ import annotations


def pick_anchor(first_visible: int, selected_row: int, bookmark_rows: list[int]) -> int | None:
    """Return the row to pin, or None.

    `first_visible` is the topmost visible view row (< 0 when the view is empty).
    `selected_row` is the current selection (< 0 for none). `bookmark_rows` are the
    view rows of visible bookmarks. Nothing pins when nothing has scrolled off the
    top (`first_visible <= 0`). Selection wins over bookmarks.
    """
    if first_visible <= 0:
        return None
    if 0 <= selected_row < first_visible:
        return selected_row
    above = [r for r in bookmark_rows if 0 <= r < first_visible]
    return max(above) if above else None
