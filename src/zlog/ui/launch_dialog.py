"""Choose an app to launch and capture (executable + arguments + working dir).

Pure view: the window reads `get_values()` and starts the reader itself.
"""

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class LaunchDialog(QDialog):
    def __init__(self, exe="", arguments="", cwd="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Launch App")
        self.resize(520, 170)

        self.exe_edit = QLineEdit(exe)
        self.exe_edit.setPlaceholderText("Path to the program to run")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        exe_row = QHBoxLayout()
        exe_row.addWidget(self.exe_edit)
        exe_row.addWidget(browse)

        self.args_edit = QLineEdit(arguments)
        self.args_edit.setPlaceholderText("Optional, e.g. --verbose --port 8080")
        self.cwd_edit = QLineEdit(cwd)
        self.cwd_edit.setPlaceholderText("Optional working directory")

        form = QFormLayout()
        form.addRow("Program", exe_row)
        form.addRow("Arguments", self.args_edit)
        form.addRow("Start in", self.cwd_edit)

        hint = QLabel(
            "zLog captures the app's console output and, on Windows, its "
            "debug output (OutputDebugString) from the first line."
        )
        hint.setWordWrap(True)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText("Launch")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(self.buttons)

        self.exe_edit.textChanged.connect(self._sync_ok)
        self._sync_ok()

    def _browse(self) -> None:
        # Windows users expect an .exe filter first; everything else still selectable.
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a program", "", "Programs (*.exe);;All files (*)"
        )
        if path:
            self.exe_edit.setText(path)
            if not self.cwd_edit.text().strip():
                self.cwd_edit.setText(os.path.dirname(path))  # sensible default

    def _sync_ok(self) -> None:
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self.exe_edit.text().strip()))

    def get_values(self) -> tuple[str, str, str]:
        """(executable, arguments, working directory) — all stripped."""
        return (
            self.exe_edit.text().strip(),
            self.args_edit.text().strip(),
            self.cwd_edit.text().strip(),
        )
