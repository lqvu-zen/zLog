"""Pick a running Docker container to attach to — see
docs/plans/docker-log-source.md.

Pure view like `LaunchDialog`/`WatchDialog`: the window supplies the initial
container list and a refresh callback; this dialog never runs `docker` itself.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from zlog.core.containers import PS_FORMAT, Container, parse_containers


def list_containers(docker_path: str = "docker", timeout: float = 5.0) -> list[Container]:
    """Running containers via `docker ps` (a short one-shot call, not a stream —
    like `adb/devices.py::list_devices`, safe to run on the UI thread).

    Raises FileNotFoundError if `docker` isn't on PATH, and
    subprocess.TimeoutExpired if the call hangs past ``timeout`` (e.g. the
    daemon isn't running) — the caller maps those to a friendly message, the
    same contract `MainWindow._run_adb` already uses for adb.
    """
    proc = subprocess.run(
        [docker_path, "ps", "--format", PS_FORMAT],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return parse_containers(proc.stdout)


class DockerDialog(QDialog):
    def __init__(self, containers: list[Container], refresh: Callable[[], None], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Attach to Docker Container")
        self.resize(420, 320)
        self._refresh = refresh

        self.list_widget = QListWidget()
        self.set_containers(containers)
        self.list_widget.itemDoubleClicked.connect(self.accept)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        top = QHBoxLayout()
        top.addWidget(QLabel("Running containers:"))
        top.addStretch(1)
        top.addWidget(refresh_btn)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText("Attach")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.list_widget.itemSelectionChanged.connect(self._sync_ok)
        self._sync_ok()

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.buttons)

    def set_containers(self, containers: list[Container]) -> None:
        """Replace the list (used both at construction and after Refresh)."""
        self.list_widget.clear()
        for c in containers:
            item = QListWidgetItem(f"{c.name}  —  {c.status}")
            item.setData(Qt.UserRole, c)
            self.list_widget.addItem(item)
        if containers:
            self.list_widget.setCurrentRow(0)

    def _sync_ok(self) -> None:
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(
            self.list_widget.currentItem() is not None
        )

    def selected_container(self) -> Container | None:
        item = self.list_widget.currentItem()
        return item.data(Qt.UserRole) if item is not None else None
