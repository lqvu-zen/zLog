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
