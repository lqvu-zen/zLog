"""Edit zLog's theme colors and save the result as a custom theme.

Pure view except for live preview: it edits its own working `Theme` (frozen
dataclass, rebuilt via `dataclasses.replace` on every change) and calls
`on_preview(theme)` so the caller (MainWindow) re-styles everything the same
way `apply_theme` already does — this dialog never touches widgets outside
itself, and never writes to `THEMES`/settings; the caller does that with
`result_theme` after `exec()` returns `Accepted`.
"""

from __future__ import annotations

from dataclasses import fields, replace

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from zlog.core.theme import BUILTIN_THEME_NAMES, Theme
from zlog.core.theme_io import HEX_RE

_LEVEL_LABELS = {
    "V": "Verbose",
    "D": "Debug",
    "I": "Info",
    "W": "Warning",
    "E": "Error",
    "F": "Fatal",
}

# (field name, row label) — every scalar hex field on Theme except `name`.
_GENERAL_FIELDS = [
    ("window", "Window background"),
    ("text", "Default text"),
    ("base", "Table background"),
    ("alt_base", "Alternating row"),
    ("header", "Header / buttons"),
    ("muted", "Muted / disabled text"),
    ("meta_text", "Time / pid / tag text"),
    ("search_error", "Invalid-regex tint"),
    ("search_highlight", "Search-highlight tint"),
    ("inline_match", "Inline match tint"),
    ("bookmark", "Bookmark marker"),
    ("button_hover", "Button hover"),
    ("button_pressed", "Button pressed"),
    ("selection_bg", "Selected row background"),
    ("selection_text", "Selected row text"),
    ("row_hover_bg", "Hovered row background"),
]

assert {f for f, _ in _GENERAL_FIELDS} | {"level_colors", "level_text", "name"} == {
    f.name for f in fields(Theme)
}  # every Theme field is either general, one of the two per-level dicts, or the name


class _ColorRow(QWidget):
    """A swatch button + hex field kept in sync; `on_change(hex)` fires from
    either the picker or a validly-typed hex (invalid text is left uncommitted
    rather than rejected outright, so typing a hex code doesn't fight you
    character by character)."""

    def __init__(self, value: str, on_change, parent=None):
        super().__init__(parent)
        self._on_change = on_change
        self.swatch = QPushButton()
        self.swatch.setFixedSize(28, 20)
        self.edit = QLineEdit(value)
        self.edit.setMaximumWidth(90)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.swatch)
        layout.addWidget(self.edit)
        layout.addStretch(1)
        self.swatch.clicked.connect(self._pick)
        self.edit.textChanged.connect(self._on_text)
        self._paint(value)

    def _paint(self, hex_value: str) -> None:
        self.swatch.setStyleSheet(f"background-color: {hex_value}; border: 1px solid #888;")

    def _on_text(self, text: str) -> None:
        if HEX_RE.match(text):
            self._paint(text)
            self._on_change(text)

    def _pick(self) -> None:
        seed = self.edit.text() if HEX_RE.match(self.edit.text()) else "#000000"
        color = QColorDialog.getColor(QColor(seed), self, "Pick a color")
        if color.isValid():
            self.set_color(color.name())

    def set_color(self, hex_value: str) -> None:
        self.edit.setText(hex_value)  # -> _on_text -> paints + notifies


class ThemeEditorDialog(QDialog):
    def __init__(self, base_theme: Theme, on_preview, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Theme")
        self.resize(420, 560)
        self._base = base_theme  # what was applied when the dialog opened (Revert/Cancel target)
        self._theme = base_theme
        self._on_preview = on_preview
        self._rows: dict[str, _ColorRow] = {}
        self.result_theme: Theme | None = None  # set on Save; caller reads it after exec()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        outer = QVBoxLayout(content)

        general = QGroupBox("General")
        form = QFormLayout(general)
        for field_name, label in _GENERAL_FIELDS:
            self._add_row(form, field_name, label, getattr(base_theme, field_name))
        outer.addWidget(general)

        bg_group = QGroupBox("Level backgrounds (row tint)")
        bg_form = QFormLayout(bg_group)
        for key in ("W", "E", "F"):
            self._add_dict_row(bg_form, "level_colors", key, base_theme.level_colors[key])
        outer.addWidget(bg_group)

        text_group = QGroupBox("Level text")
        text_form = QFormLayout(text_group)
        for key in ("V", "D", "I", "W", "E", "F"):
            self._add_dict_row(text_form, "level_text", key, base_theme.level_text[key])
        outer.addWidget(text_group)
        outer.addStretch(1)

        scroll.setWidget(content)

        revert_btn = QPushButton("Revert")
        revert_btn.clicked.connect(self._revert)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.addButton(revert_btn, QDialogButtonBox.ResetRole)
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self._cancel)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addWidget(self.buttons)

    def _add_row(self, form: QFormLayout, field_name: str, label: str, value: str) -> None:
        row = _ColorRow(value, lambda v, f=field_name: self._set(f, v))
        self._rows[field_name] = row
        form.addRow(label, row)

    def _add_dict_row(self, form: QFormLayout, field_name: str, key: str, value: str) -> None:
        row = _ColorRow(value, lambda v, f=field_name, k=key: self._set_dict(f, k, v))
        self._rows[f"{field_name}.{key}"] = row
        form.addRow(_LEVEL_LABELS[key], row)

    def _set(self, field_name: str, value: str) -> None:
        self._theme = replace(self._theme, **{field_name: value})
        self._on_preview(self._theme)

    def _set_dict(self, field_name: str, key: str, value: str) -> None:
        updated = dict(getattr(self._theme, field_name))
        updated[key] = value
        self._theme = replace(self._theme, **{field_name: updated})
        self._on_preview(self._theme)

    def _revert(self) -> None:
        self._theme = self._base
        self._on_preview(self._theme)
        for field_name, row in self._rows.items():
            if "." in field_name:
                parent, key = field_name.split(".")
                row.set_color(getattr(self._base, parent)[key])
            else:
                row.set_color(getattr(self._base, field_name))

    def _cancel(self) -> None:
        self._on_preview(self._base)  # undo any live preview
        self.reject()

    def _save(self) -> None:
        default_name = self._base.name if self._base.name not in BUILTIN_THEME_NAMES else "My Theme"
        while True:
            name, ok = QInputDialog.getText(self, "Save Theme", "Theme name:", text=default_name)
            if not ok:
                return  # back to editing; the live preview stays as-is
            name = name.strip()
            if not name:
                continue
            if name in BUILTIN_THEME_NAMES:
                QMessageBox.warning(self, "Name unavailable", f'"{name}" is a built-in theme name.')
                default_name = name
                continue
            break
        self.result_theme = replace(self._theme, name=name)
        self.accept()
