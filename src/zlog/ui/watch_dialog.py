"""Watch-pattern editor: the substring to notify on, plus an optional command
to run on a hit.

Pure view: it knows nothing about matching or process spawning — the window
reads back `get_values()` and does that itself.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class WatchDialog(QDialog):
    def __init__(self, pattern="", command="", webhook="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Watch Pattern")
        self.resize(460, 190)

        self.pattern_edit = QLineEdit(pattern)
        self.pattern_edit.setPlaceholderText("Notify on lines containing… (blank to clear)")
        self.command_edit = QLineEdit(command)
        self.command_edit.setPlaceholderText("e.g. myscript.exe {tag} {message}  (optional)")
        self.webhook_edit = QLineEdit(webhook)
        self.webhook_edit.setPlaceholderText("e.g. https://hooks.example.com/…  (optional)")

        form = QFormLayout()
        form.addRow("Pattern", self.pattern_edit)
        form.addRow("Run command", self.command_edit)
        form.addRow("Webhook URL", self.webhook_edit)

        hint = QLabel(
            "Command placeholders: {message} {tag} {pid} {level} {time} {line}. Runs "
            "without a shell — never types requiring shell features (pipes, &&, etc.).\n"
            "Webhook: a JSON POST with the same fields, off the UI thread. The URL is "
            "stored in plain text in zLog's settings file, like other saved paths."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(self.buttons)

    def get_values(self) -> tuple[str, str, str]:
        return (
            self.pattern_edit.text(),
            self.command_edit.text().strip(),
            self.webhook_edit.text().strip(),
        )
