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
    meta_text: str  # time/pid/tag columns in the log (readable, not as loud as text)
    level_colors: dict[str, str]  # W/E/F -> row tint hex
    search_error: str  # invalid-regex box tint hex
    search_highlight: str  # tint for rows matching the search in highlight mode
    inline_match: str  # tint behind the matched substring itself (on top of the row tint)
    bookmark: str  # bookmark marker color (decoration on the Time column)
    level_text: dict[str, str]  # per-level message text color (V/D/I/W/E/F)
    button_hover: str  # QPushButton background when hovered
    button_pressed: str  # QPushButton background when pressed
    selection_bg: str  # selected log row background
    selection_text: str  # selected log row text
    row_hover_bg: str  # hovered (not selected) log row background


LIGHT = Theme(
    name="Light",
    window="#f3f3f3",
    text="#1e1e1e",
    base="#ffffff",
    alt_base="#f7f7f7",
    header="#e8e8e8",
    muted="#9aa0a6",
    meta_text="#5f6368",
    level_colors={"W": "#fff4c8", "E": "#ffd7d7", "F": "#ffbebe"},
    search_error="#ffd7d7",
    search_highlight="#cfe8ff",
    inline_match="#8ec4f5",
    bookmark="#1a73e8",
    level_text={
        "V": "#6a6a6a",
        "D": "#3b6ea5",
        "I": "#2e7d32",
        "W": "#8a6d00",
        "E": "#c62828",
        "F": "#b71c1c",
    },
    button_hover="#dcdcdc",
    button_pressed="#cfcfcf",
    selection_bg="#2b6cdb",
    selection_text="#ffffff",
    row_hover_bg="#dbe9fb",
)

DARK = Theme(
    name="Dark",
    window="#1e1e1e",
    text="#d4d4d4",
    base="#252526",
    alt_base="#2d2d2e",
    header="#333333",
    muted="#8a8a8a",
    meta_text="#b7bcc2",
    level_colors={"W": "#4d4526", "E": "#5a2b2b", "F": "#742b2b"},
    search_error="#5a2b2b",
    search_highlight="#33506b",
    inline_match="#5c86ab",
    bookmark="#4da3ff",
    level_text={
        "V": "#9aa0a6",
        "D": "#7fa8d0",
        "I": "#7ec699",
        "W": "#d7c04d",
        "E": "#f28b82",
        "F": "#ff6b6b",
    },
    button_hover="#3d3d3d",
    button_pressed="#474747",
    selection_bg="#2f6fbf",
    selection_text="#ffffff",
    row_hover_bg="#37475c",
)

THEMES: dict[str, Theme] = {LIGHT.name: LIGHT, DARK.name: DARK}


def build_stylesheet(theme: Theme) -> str:
    """Return app-wide QSS for the given theme."""
    return (
        f"QWidget {{ background-color: {theme.window}; color: {theme.text}; }}\n"
        f"QTableView {{ background-color: {theme.base}; color: {theme.text};\n"
        f"    alternate-background-color: {theme.alt_base};\n"
        f"    gridline-color: {theme.header}; }}\n"
        # The unconditional `color` above only applies to unselected, unhovered
        # cells — without explicit hover/selected rules, the background those
        # states get isn't guaranteed to pair legibly with that text color.
        # Hover is listed first so :selected wins (source order) when a row is
        # both hovered and selected at once.
        f"QTableView::item:hover {{ background-color: {theme.row_hover_bg};\n"
        f"    color: {theme.text}; }}\n"
        f"QTableView::item:selected {{ background-color: {theme.selection_bg};\n"
        f"    color: {theme.selection_text}; }}\n"
        f"QHeaderView::section {{ background-color: {theme.header}; color: {theme.text};\n"
        f"    border: 0px; padding: 2px 6px; }}\n"
        f"QLineEdit, QComboBox {{ background-color: {theme.base}; color: {theme.text}; }}\n"
        f"QComboBox QAbstractItemView {{ background-color: {theme.base}; color: {theme.text}; }}\n"
        # Same fixed-color caveat as the table: once the item view has an explicit
        # `color`, Qt stops swapping it for the highlighted row, so the OS-painted
        # highlight background can clash with it. Pin both states to the same
        # tokens the log table uses (hover first so :selected wins on source order),
        # so a dropdown item stays legible regardless of the OS accent color.
        f"QComboBox QAbstractItemView::item:hover {{ background-color: {theme.row_hover_bg};\n"
        f"    color: {theme.text}; }}\n"
        f"QComboBox QAbstractItemView::item:selected {{ background-color: {theme.selection_bg};\n"
        f"    color: {theme.selection_text}; }}\n"
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
        # Styling the indicator's border replaces Qt's native check glyph, so the
        # checked state needs its own look or on/off render as the same empty box.
        # Give unchecked a visible bordered box and fill checked with the selection
        # accent so it's unmistakably on.
        f"QCheckBox::indicator {{ width: 14px; height: 14px; border-radius: 3px;\n"
        f"    border: 1px solid {theme.muted}; background-color: {theme.base}; }}\n"
        f"QCheckBox::indicator:checked {{ background-color: {theme.selection_bg};\n"
        f"    border-color: {theme.selection_bg}; }}\n"
    )
