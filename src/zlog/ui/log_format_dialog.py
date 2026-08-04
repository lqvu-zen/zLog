"""The Log Formats manager: add/edit/remove user-defined `LogFormat`s with a
live preview against pasted sample lines.

Pure Qt view, same contract as `HighlightRulesDialog`/`SettingsDialog`: takes
the current formats in, returns the edited *user* list via `get_values()`.
MainWindow owns applying/persisting them and never has this module import it
back (see main-window-drift.md).
"""

from __future__ import annotations

import dataclasses
import re

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zlog.core.logformat import (
    LogFormat,
    aliases_to_text,
    apply_aliases,
    parse_aliases_text,
    time_pattern,
)

_FIELD_COLUMNS = ("time", "pid", "tid", "level", "tag", "message")
# Preview-time warning threshold. Calibrated against a classic catastrophic
# pattern ((a+)+$): ~27ms at the probe length core.logformat uses, versus
# ~0.02ms for a normal pattern — comfortably separated, so this can sit close
# to the catastrophic case without false-positiving on ordinary regexes.
_SLOW_PATTERN_SECONDS = 0.01


class LogFormatDialog(QDialog):
    def __init__(self, formats: list[LogFormat], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log Formats")
        self.resize(760, 520)
        # Working copy in display order (built-ins first, unchanged elsewhere).
        self._formats: list[LogFormat] = list(formats)
        self._current = -1  # index into self._formats of the selected row

        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._select)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add)
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove)
        list_buttons = QHBoxLayout()
        list_buttons.addWidget(add_btn)
        list_buttons.addWidget(self.remove_btn)
        left = QVBoxLayout()
        left.addWidget(QLabel("Formats (built-ins are read-only):"))
        left.addWidget(self.list)
        left.addLayout(list_buttons)
        left_widget = QWidget()
        left_widget.setLayout(left)

        self.name_edit = QLineEdit()
        self.name_edit.textEdited.connect(self._on_name_edited)
        self.pattern_edit = QLineEdit()
        self.pattern_edit.setPlaceholderText(
            r"^(?P<time>...)\s+(?P<level>\w+)\s+(?P<tag>.*?):\s?(?P<message>.*)$"
        )
        self.pattern_edit.textEdited.connect(self._on_pattern_edited)
        self.aliases_edit = QPlainTextEdit()
        self.aliases_edit.setPlaceholderText("ERROR=E\nWARN=W\nFATAL=F")
        self.aliases_edit.setMaximumHeight(80)
        self.aliases_edit.textChanged.connect(self._on_aliases_edited)
        self.samples_edit = QPlainTextEdit()
        self.samples_edit.setPlaceholderText("Paste a few representative lines, one per row…")
        self.samples_edit.setMaximumHeight(100)
        self.samples_edit.textChanged.connect(self._update_preview)

        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: #b00020;")
        self.warning_label.setWordWrap(True)

        self.preview = QTableWidget(0, 1 + len(_FIELD_COLUMNS))
        self.preview.setHorizontalHeaderLabels(
            ["Line", "Time", "PID", "TID", "Level", "Tag", "Message"]
        )
        self.preview.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.preview.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.preview.verticalHeader().setVisible(False)

        editor = QVBoxLayout()
        editor.addWidget(QLabel("Name:"))
        editor.addWidget(self.name_edit)
        editor.addWidget(QLabel("Pattern (named groups: time, pid, tid, level, tag, message):"))
        editor.addWidget(self.pattern_edit)
        editor.addWidget(
            QLabel("Level aliases (one SPELLING=X per line; unmapped levels stay unparsed):")
        )
        editor.addWidget(self.aliases_edit)
        editor.addWidget(QLabel("Sample lines:"))
        editor.addWidget(self.samples_edit)
        editor.addWidget(self.warning_label)
        editor.addWidget(QLabel("Live preview:"))
        editor.addWidget(self.preview)
        editor_widget = QWidget()
        editor_widget.setLayout(editor)

        splitter = QSplitter()
        splitter.addWidget(left_widget)
        splitter.addWidget(editor_widget)
        splitter.setStretchFactor(1, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(splitter, 1)
        root.addWidget(buttons)

        self._reload_list()
        if self._formats:
            self.list.setCurrentRow(0)

    # --- list management -----------------------------------------------
    def _reload_list(self, select: int | None = None) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for f in self._formats:
            label = f"{f.name} (built-in)" if f.builtin else f.name
            item = QListWidgetItem(label)
            self.list.addItem(item)
        self.list.blockSignals(False)
        if select is not None and 0 <= select < self.list.count():
            self.list.setCurrentRow(select)

    def _add(self) -> None:
        new = LogFormat(name=f"New Format {len(self._formats) + 1}", pattern="", level_aliases={})
        self._formats.append(new)
        self._reload_list(select=len(self._formats) - 1)

    def _remove(self) -> None:
        if self._current < 0 or self._formats[self._current].builtin:
            return
        removed = self._current
        del self._formats[removed]
        self._current = -1
        self._reload_list(select=min(removed, len(self._formats) - 1))

    # --- selection --------------------------------------------------------
    def _select(self, row: int) -> None:
        self._current = row
        editable = 0 <= row < len(self._formats) and not self._formats[row].builtin
        self.remove_btn.setEnabled(editable)
        self.name_edit.setEnabled(editable)
        self.pattern_edit.setEnabled(editable)
        self.aliases_edit.setEnabled(editable)
        if 0 <= row < len(self._formats):
            f = self._formats[row]
            self.name_edit.blockSignals(True)
            self.pattern_edit.blockSignals(True)
            self.aliases_edit.blockSignals(True)
            self.name_edit.setText(f.name)
            self.pattern_edit.setText(f.pattern)
            self.aliases_edit.setPlainText(aliases_to_text(f.level_aliases))
            self.name_edit.blockSignals(False)
            self.pattern_edit.blockSignals(False)
            self.aliases_edit.blockSignals(False)
        self._update_preview()

    # --- live editing -------------------------------------------------
    def _replace_current(self, **changes) -> None:
        if self._current < 0 or self._formats[self._current].builtin:
            return
        self._formats[self._current] = dataclasses.replace(self._formats[self._current], **changes)

    def _on_name_edited(self, text: str) -> None:
        self._replace_current(name=text)
        item = self.list.item(self._current)
        if item is not None:
            item.setText(text)

    def _on_pattern_edited(self, text: str) -> None:
        self._replace_current(pattern=text)
        self._update_preview()

    def _on_aliases_edited(self) -> None:
        self._replace_current(level_aliases=parse_aliases_text(self.aliases_edit.toPlainText()))
        self._update_preview()

    # --- preview --------------------------------------------------------
    def _update_preview(self) -> None:
        self.preview.setRowCount(0)
        self.warning_label.setText("")
        if self._current < 0 or self._current >= len(self._formats):
            return
        fmt = self._formats[self._current]
        lines = [ln for ln in self.samples_edit.toPlainText().splitlines() if ln.strip()]
        if not fmt.pattern or not lines:
            return
        try:
            rx = re.compile(fmt.pattern)
        except re.error as exc:
            self.warning_label.setText(f"Invalid regex: {exc}")
            return
        for line in lines:
            row = self.preview.rowCount()
            self.preview.insertRow(row)
            self.preview.setItem(row, 0, QTableWidgetItem(line))
            m = rx.match(line)
            if not m:
                for col in range(1, self.preview.columnCount()):
                    self.preview.setItem(row, col, QTableWidgetItem("(no match)"))
                continue
            g = m.groupdict()
            for col, field_name in enumerate(_FIELD_COLUMNS, start=1):
                value = g.get(field_name) or ""
                if field_name == "level" and value:
                    mapped = apply_aliases(value, fmt.level_aliases)
                    value = mapped or f"{value} (unmapped -> unparsed)"
                self.preview.setItem(row, col, QTableWidgetItem(value))
        elapsed = time_pattern(fmt.pattern, lines)
        if elapsed > _SLOW_PATTERN_SECONDS:
            self.warning_label.setText(
                f"This pattern took {elapsed * 1000:.0f}ms against the samples — check for nested "
                "quantifiers before using it on a large file."
            )

    # --- result -------------------------------------------------------
    def get_values(self) -> list[LogFormat]:
        """The edited user formats (built-ins excluded — they're code, not
        settings, and never round-trip through this dialog)."""
        return [f for f in self._formats if not f.builtin]
