"""Color themes for zLog — pure config, no Qt, so it's unit-testable.

The model turns the per-level hex values into `QColor`; `main_window` applies
`build_stylesheet` to the `QApplication`. Keeping colors here means no widget
hard-codes a hex value.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    window: str  # window / chrome background
    text: str  # default foreground
    base: str  # table / input background
    alt_base: str  # alternating row background
    header: str  # header + button background, gridlines
    muted: str  # disabled/secondary text
    level_colors: dict[str, str]  # W/E/F -> row tint hex
    search_error: str  # invalid-regex box tint hex
    search_highlight: str  # tint for rows matching the search in highlight mode
    bookmark: str  # bookmark marker color (decoration on the Time column)
    button_hover: str  # QPushButton background when hovered
    button_pressed: str  # QPushButton background when pressed


LIGHT = Theme(
    name="Light",
    window="#f3f3f3",
    text="#1e1e1e",
    base="#ffffff",
    alt_base="#f7f7f7",
    header="#e8e8e8",
    muted="#9aa0a6",
    level_colors={"W": "#fff4c8", "E": "#ffd7d7", "F": "#ffbebe"},
    search_error="#ffd7d7",
    search_highlight="#cfe8ff",
    bookmark="#1a73e8",
    button_hover="#dcdcdc",
    button_pressed="#cfcfcf",
)

DARK = Theme(
    name="Dark",
    window="#1e1e1e",
    text="#d4d4d4",
    base="#252526",
    alt_base="#2d2d2e",
    header="#333333",
    muted="#8a8a8a",
    level_colors={"W": "#4d4526", "E": "#5a2b2b", "F": "#742b2b"},
    search_error="#5a2b2b",
    search_highlight="#33506b",
    bookmark="#4da3ff",
    button_hover="#3d3d3d",
    button_pressed="#474747",
)

THEMES: dict[str, Theme] = {LIGHT.name: LIGHT, DARK.name: DARK}


def build_stylesheet(theme: Theme) -> str:
    """Return app-wide QSS for the given theme."""
    return (
        f"QWidget {{ background-color: {theme.window}; color: {theme.text}; }}\n"
        f"QTableView {{ background-color: {theme.base}; color: {theme.text};\n"
        f"    alternate-background-color: {theme.alt_base};\n"
        f"    gridline-color: {theme.header}; }}\n"
        f"QHeaderView::section {{ background-color: {theme.header}; color: {theme.text};\n"
        f"    border: 0px; padding: 2px 6px; }}\n"
        f"QLineEdit, QComboBox {{ background-color: {theme.base}; color: {theme.text}; }}\n"
        f"QComboBox QAbstractItemView {{ background-color: {theme.base}; color: {theme.text}; }}\n"
        # A stylesheet background-color disables Qt's automatic hover/pressed
        # variation, so both states need an explicit rule or clicking a button
        # gives no visual feedback at all. The border also gets its own color
        # (rather than matching the fill) so buttons read as bordered controls
        # at rest, not flat rectangles.
        f"QPushButton {{ background-color: {theme.header}; color: {theme.text};\n"
        f"    border: 1px solid {theme.muted}; padding: 3px 10px; }}\n"
        f"QPushButton:hover {{ background-color: {theme.button_hover}; }}\n"
        f"QPushButton:pressed {{ background-color: {theme.button_pressed}; }}\n"
        f"QPushButton:disabled {{ color: {theme.muted}; }}\n"
        f"QMenuBar, QMenu {{ background-color: {theme.window}; color: {theme.text}; }}\n"
        f"QStatusBar {{ color: {theme.text}; }}\n"
        # The native unchecked-indicator border is too faint against a dark
        # chrome background to scan at a glance; give it explicit contrast.
        f"QCheckBox::indicator {{ border: 1px solid {theme.muted}; }}\n"
    )
