"""A small Name + Query editor for saved filters (Add / Edit).

Pure view: it knows nothing about presets or the model — the window reads back
`get_values()` and builds/updates the preset itself.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)


class PresetDialog(QDialog):
    def __init__(self, title, name="", query="", name_editable=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(460, 120)

        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText("Preset name")
        self.name_edit.setEnabled(name_editable)  # Edit keeps the name (use Rename)
        self.query_edit = QLineEdit(query)
        self.query_edit.setPlaceholderText("e.g. level:E tag:Activity -Gnss")

        form = QFormLayout()
        form.addRow("Name", self.name_edit)
        form.addRow("Query", self.query_edit)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

        # A preset must be named; block OK until it is (only relevant to Add).
        self.name_edit.textChanged.connect(self._sync_ok)
        self._sync_ok()

    def _sync_ok(self) -> None:
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self.name_edit.text().strip()))

    def get_values(self) -> tuple[str, str]:
        return self.name_edit.text().strip(), self.query_edit.text()
