"""Color themes for zLog — the data lives in `core/theme.py` (Qt-free, so a
custom theme can be validated without a display); this module adds the
Qt-facing pieces: QSS generation and mutating the registry with a user's
custom theme.

The model turns the per-level hex values into `QColor`; `main_window` applies
`build_stylesheet` to the `QApplication`. Keeping colors in `core/` means no
widget hard-codes a hex value.
"""

from __future__ import annotations

from zlog.core.theme import (
    BUILTIN_THEME_NAMES,
    DARK,
    LIGHT,
    MONOKAI,
    SOLARIZED_DARK,
    THEMES,
    Theme,
)

__all__ = [
    "BUILTIN_THEME_NAMES",
    "DARK",
    "LIGHT",
    "MONOKAI",
    "SOLARIZED_DARK",
    "THEMES",
    "Theme",
    "build_stylesheet",
    "register_theme",
]


def register_theme(theme: Theme) -> None:
    """Add or replace a custom theme in `THEMES` at runtime. Built-in themes
    can never be overwritten this way — raises `ValueError` if `theme.name`
    collides with one (the theme editor is expected to reject that name
    before ever calling this)."""
    if theme.name in BUILTIN_THEME_NAMES:
        raise ValueError(f"{theme.name!r} is a built-in theme name")
    THEMES[theme.name] = theme


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
        # A bare QTabBar (no QTabWidget pane) renders its selected tab as a
        # floating bordered pill in the native style — which looks like a stray
        # text box when there's only one tab. Flatten tabs to an underline style
        # (transparent tab, accent bottom-border when selected) so one tab reads
        # as a plain label and many tabs read as a clean strip.
        f"QTabBar {{ border: none; }}\n"
        f"QTabBar::tab {{ background: transparent; color: {theme.muted};\n"
        f"    border: none; border-bottom: 2px solid transparent; padding: 4px 12px; }}\n"
        f"QTabBar::tab:selected {{ color: {theme.text};\n"
        f"    border-bottom: 2px solid {theme.selection_bg}; }}\n"
        f"QTabBar::tab:hover {{ color: {theme.text}; }}\n"
        # The new-tab (+) button sits in the tab strip, so it's flat too — a
        # bordered button there would reintroduce the boxy look we just removed.
        f"QPushButton#newTabButton {{ border: none; background: transparent;\n"
        f"    color: {theme.muted}; padding: 0; font-weight: bold; }}\n"
        f"QPushButton#newTabButton:hover {{ color: {theme.text};\n"
        f"    background-color: {theme.button_hover}; }}\n"
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
        # The global `QWidget { background-color }` above cascades onto scrollbars and
        # flattens them, so the draggable handle becomes invisible against the groove.
        # Style the handle explicitly (a `muted` thumb over a `header` groove) so it
        # reads as a real scrollbar; the HeatScrollBar still paints its error ticks on
        # top. Hidden arrow buttons keep it clean.
        f"QScrollBar:vertical {{ background: {theme.header}; width: 14px; margin: 0; }}\n"
        f"QScrollBar::handle:vertical {{ background: {theme.muted}; min-height: 28px;\n"
        f"    border-radius: 3px; margin: 1px; }}\n"
        f"QScrollBar::handle:vertical:hover {{ background: {theme.meta_text}; }}\n"
        f"QScrollBar:horizontal {{ background: {theme.header}; height: 14px; margin: 0; }}\n"
        f"QScrollBar::handle:horizontal {{ background: {theme.muted}; min-width: 28px;\n"
        f"    border-radius: 3px; margin: 1px; }}\n"
        f"QScrollBar::handle:horizontal:hover {{ background: {theme.meta_text}; }}\n"
        f"QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}\n"
        f"QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}\n"
    )
