"""Configure the network listener's bind address and port — see
docs/plans/network-log-source.md.

Pure view: the window reads `get_values()` and starts the reader itself.
Loopback-only is the default; reaching other machines is an explicit,
separately-labeled opt-in, never the default for a dev tool that opens a
listening socket.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class NetworkDialog(QDialog):
    def __init__(self, last_port: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Listen on Network")
        self.resize(420, 170)

        self.port_edit = QLineEdit(str(last_port) if last_port else "")
        self.port_edit.setPlaceholderText("0 = choose an available port")
        self.remote_check = QCheckBox("Allow connections from other machines (binds 0.0.0.0)")
        self.remote_check.setChecked(False)

        form = QFormLayout()
        form.addRow("Port", self.port_edit)
        form.addRow("", self.remote_check)

        hint = QLabel(
            "Loopback only (127.0.0.1) unless the box above is checked — only enable "
            "that on a trusted network, since anything that can reach the port can "
            "send lines into this tab."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText("Listen")
        self.buttons.accepted.connect(self._accept_if_valid)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(self.buttons)

    def _accept_if_valid(self) -> None:
        if self._port_value() is None:
            self.port_edit.setStyleSheet("border: 1px solid #c62828;")
            return
        self.accept()

    def _port_value(self) -> int | None:
        text = self.port_edit.text().strip()
        if not text:
            return 0
        if not text.isdigit():
            return None
        port = int(text)
        return port if 0 <= port <= 65535 else None

    def get_values(self) -> tuple[str, int]:
        """(host, port) — host is `0.0.0.0` only when explicitly opted in."""
        host = "0.0.0.0" if self.remote_check.isChecked() else "127.0.0.1"
        return host, self._port_value() or 0
