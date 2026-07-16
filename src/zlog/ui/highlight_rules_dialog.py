"""A dialog for managing persistent highlight rules (term/regex -> color).

Pure Qt view: it takes the current rules and returns the edited list via
``get_values()``. The MainWindow owns *applying* and persisting them (via
LogTableModel.set_highlight_rules + the settings-spec table), so this dialog
stays decoupled and unit-testable without a running window — same contract as
SettingsDialog.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

_DEFAULT_COLOR = "#ffeb3b"


class HighlightRulesDialog(QDialog):
    def __init__(self, rules: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Highlight Rules")
        self.setMinimumWidth(440)
        self.resize(440, 360)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Pattern", "Regex", "Color"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for rule in rules:
            self._add_row(
                rule.get("pattern", ""), rule.get("regex", False), rule.get("color", _DEFAULT_COLOR)
            )

        add_btn = QPushButton("Add Rule")
        add_btn.clicked.connect(lambda: self._add_row("", False, _DEFAULT_COLOR))
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(
            QLabel(
                "Rows matching a pattern below are always tinted, regardless of\nthe active search."
            )
        )
        root.addWidget(self.table)
        root.addLayout(btn_row)
        root.addWidget(buttons)

    def _add_row(self, pattern: str, regex: bool, color: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(pattern))
        check = QCheckBox()
        check.setChecked(bool(regex))
        cell = QWidget()
        layout = QHBoxLayout(cell)
        layout.addWidget(check)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(check, Qt.AlignCenter)
        self.table.setCellWidget(row, 1, cell)
        swatch = QPushButton()
        swatch.setProperty("_color", color or _DEFAULT_COLOR)
        swatch.setStyleSheet(f"background-color: {color or _DEFAULT_COLOR};")
        swatch.clicked.connect(lambda _c=False, r=row: self._pick_color(r))
        self.table.setCellWidget(row, 2, swatch)

    def _pick_color(self, row: int) -> None:
        swatch = self.table.cellWidget(row, 2)
        picked = QColorDialog.getColor(parent=self, title="Highlight color")
        if picked.isValid():
            swatch.setProperty("_color", picked.name())
            swatch.setStyleSheet(f"background-color: {picked.name()};")

    def _remove_selected(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)

    def get_values(self) -> list[dict]:
        out = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            pattern = item.text().strip() if item else ""
            if not pattern:
                continue
            cell = self.table.cellWidget(row, 1)
            check = cell.findChild(QCheckBox) if cell is not None else None
            regex = check.isChecked() if check is not None else False
            swatch = self.table.cellWidget(row, 2)
            color = swatch.property("_color") if swatch is not None else _DEFAULT_COLOR
            out.append({"pattern": pattern, "regex": regex, "color": color or _DEFAULT_COLOR})
        return out
