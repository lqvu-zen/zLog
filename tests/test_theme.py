"""Tests for the color themes. Pure config — no Qt, no display required."""

from zlog.ui.theme import DARK, LIGHT, THEMES, build_stylesheet


def test_themes_present():
    assert set(THEMES) == {"Light", "Dark"}


def test_level_colors_are_hex():
    for theme in THEMES.values():
        for level in ("W", "E", "F"):
            color = theme.level_colors[level]
            assert color.startswith("#") and len(color) == 7


def test_search_error_is_hex():
    assert LIGHT.search_error.startswith("#")
    assert DARK.search_error.startswith("#")


def test_stylesheet_contains_theme_colors():
    qss = build_stylesheet(DARK)
    assert DARK.window in qss
    assert DARK.base in qss
    assert "QTableView" in qss


def test_search_highlight_is_hex():
    for theme in THEMES.values():
        assert theme.search_highlight.startswith("#") and len(theme.search_highlight) == 7


def test_bookmark_is_hex():
    for theme in THEMES.values():
        assert theme.bookmark.startswith("#") and len(theme.bookmark) == 7


def test_selection_colors_are_hex_and_styled():
    for theme in THEMES.values():
        assert theme.selection_bg.startswith("#") and len(theme.selection_bg) == 7
        assert theme.selection_text.startswith("#") and len(theme.selection_text) == 7
    qss = build_stylesheet(DARK)
    assert "QTableView::item:selected" in qss
    assert DARK.selection_bg in qss
    assert DARK.selection_text in qss


def test_row_hover_is_hex_and_styled_before_selected():
    for theme in THEMES.values():
        assert theme.row_hover_bg.startswith("#") and len(theme.row_hover_bg) == 7
    qss = build_stylesheet(DARK)
    assert "QTableView::item:hover" in qss
    assert DARK.row_hover_bg in qss
    # Hover must come first so :selected wins (source order) when a row is
    # both hovered and selected.
    assert qss.index("::item:hover") < qss.index("::item:selected")
