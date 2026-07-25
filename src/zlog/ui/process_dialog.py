"""Pick a running process to focus the log view on.

Pure view: it lists what it's given (or `list_processes()` by default) and hands
back the chosen `ProcessInfo` — the window decides how to rewrite the query.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from zlog.core.procinfo import filter_processes
from zlog.winlog.processes import list_processes


class ProcessPickerDialog(QDialog):
    def __init__(self, processes=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Focus App")
        self.resize(420, 460)
        # Injectable for tests; otherwise enumerate live.
        self._all = list(processes) if processes is not None else list_processes()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name or PID…")
        self.search.setClearButtonEnabled(True)
        self.list = QListWidget()
        self.empty_label = QLabel("No processes found (this is a Windows-only list).")
        self.empty_label.setWordWrap(True)
        # Focusing by name survives the app restarting; by PID is exact but dies
        # with the process — so name is the default and PID is opt-in.
        self.pid_only = QCheckBox("This PID only (don't follow restarts)")
        self.refresh_btn = QPushButton("Refresh")

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.list)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.pid_only)
        layout.addWidget(self.refresh_btn)
        layout.addWidget(self.buttons)

        self.search.textChanged.connect(self._repopulate)
        self.refresh_btn.clicked.connect(self._refresh)
        self.list.itemSelectionChanged.connect(self._sync_ok)
        self.list.itemDoubleClicked.connect(lambda _item: self.accept())
        self._repopulate()

    def _refresh(self) -> None:
        self._all = list_processes()
        self._repopulate()

    def _repopulate(self) -> None:
        self.list.clear()
        for proc in filter_processes(self._all, self.search.text()):
            item = QListWidgetItem(proc.label)
            item.setData(0x0100, proc)  # Qt.UserRole
            self.list.addItem(item)
        self.empty_label.setVisible(self.list.count() == 0)
        self._sync_ok()

    def _sync_ok(self) -> None:
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(self.list.currentItem() is not None)

    def selected(self):
        """The chosen `ProcessInfo`, or None."""
        item = self.list.currentItem()
        return item.data(0x0100) if item else None

    def focus_by_pid(self) -> bool:
        return self.pid_only.isChecked()
