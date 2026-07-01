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
        f"QPushButton {{ background-color: {theme.header}; color: {theme.text};\n"
        f"    border: 1px solid {theme.header}; padding: 3px 10px; }}\n"
        f"QPushButton:disabled {{ color: {theme.muted}; }}\n"
        f"QMenuBar, QMenu {{ background-color: {theme.window}; color: {theme.text}; }}\n"
        f"QStatusBar {{ color: {theme.text}; }}\n"
    )
