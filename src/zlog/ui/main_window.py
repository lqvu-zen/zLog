"""The main window: wires the reader, model, filters and table together.

Data flow:

    AdbReader (thread) --batch_ready--> LogTableModel (master list)
                                              |
                                        LogFilterProxy (level + text + package PIDs)
                                              |
                                         QTableView (what you see)
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from zlog.adb.devices import list_devices
from zlog.adb.packages import list_packages, resolve_pids
from zlog.adb.reader import AdbReader
from zlog.core.devices import Device
from zlog.core.session import entries_to_text, text_to_entries
from zlog.ui.log_model import MESSAGE_COL, LogFilterProxy, LogTableModel

LEVELS = ["V", "D", "I", "W", "E", "F"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("zLog — Android Log Viewer")
        self.resize(1100, 700)

        # model + proxy + view
        self.model = LogTableModel(self)
        self.proxy = LogFilterProxy(self)
        self.proxy.setSourceModel(self.model)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(MESSAGE_COL, QHeaderView.Stretch)

        # --- row 1: device + stream controls ---
        self.device_box = QComboBox()
        self.device_box.setMinimumWidth(180)
        self.refresh_btn = QPushButton("Refresh")
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.clear_btn = QPushButton("Clear")
        self.stop_btn.setEnabled(False)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Device:"))
        row1.addWidget(self.device_box)
        row1.addWidget(self.refresh_btn)
        row1.addSpacing(16)
        row1.addWidget(self.start_btn)
        row1.addWidget(self.stop_btn)
        row1.addWidget(self.clear_btn)
        row1.addStretch(1)

        # --- row 2: filters ---
        self.package_box = QComboBox()
        self.package_box.setEditable(True)
        self.package_box.setMinimumWidth(220)
        self.package_box.lineEdit().setPlaceholderText("Package, e.g. com.example.app")
        self.load_pkgs_btn = QPushButton("Load")
        self.apply_pkg_btn = QPushButton("Filter")
        self.clear_pkg_btn = QPushButton("Clear pkg")

        self.level_box = QComboBox()
        for letter in LEVELS:
            self.level_box.addItem(letter, letter)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by tag or message…")
        self.regex_check = QCheckBox("Regex")

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Package:"))
        row2.addWidget(self.package_box)
        row2.addWidget(self.load_pkgs_btn)
        row2.addWidget(self.apply_pkg_btn)
        row2.addWidget(self.clear_pkg_btn)
        row2.addSpacing(16)
        row2.addWidget(QLabel("Min level:"))
        row2.addWidget(self.level_box)
        row2.addWidget(self.search, stretch=1)
        row2.addWidget(self.regex_check)

        layout = QVBoxLayout()
        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addWidget(self.table)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.setStatusBar(QStatusBar())

        # File menu: Open / Save log
        file_menu = self.menuBar().addMenu("&File")
        open_act = file_menu.addAction("&Open Log…")
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_log)
        save_act = file_menu.addAction("&Save Log…")
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_log)

        self.reader: AdbReader | None = None
        self._devices: list[Device] = []

        # connections
        self.refresh_btn.clicked.connect(self.refresh_devices)
        self.device_box.currentIndexChanged.connect(self._update_start_enabled)
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.clear_btn.clicked.connect(self.model.clear)
        self.load_pkgs_btn.clicked.connect(self.load_packages)
        self.apply_pkg_btn.clicked.connect(self.apply_package_filter)
        self.clear_pkg_btn.clicked.connect(self.clear_package_filter)
        self.package_box.lineEdit().returnPressed.connect(self.apply_package_filter)
        self.level_box.currentIndexChanged.connect(
            lambda: self.proxy.set_min_level(self.level_box.currentData())
        )
        self.search.textChanged.connect(self._apply_search)
        self.regex_check.toggled.connect(self._apply_search)

        # initial device scan
        self.refresh_devices()

    # --- devices -----------------------------------------------------------
    def refresh_devices(self) -> None:
        try:
            devices = list_devices()
        except FileNotFoundError:
            self._show_device_error(
                "adb not found — install Android platform-tools and add it to PATH."
            )
            return
        except Exception as exc:  # timeout or other adb failure
            self._show_device_error(f"Could not list devices: {exc}")
            return
        self._populate_devices(devices)

    def _populate_devices(self, devices: list[Device]) -> None:
        """Fill the picker from a device list (also called by the run-zlog driver
        with fake devices, so it stays free of subprocess calls)."""
        self._devices = list(devices)
        self.device_box.clear()
        if not devices:
            self.device_box.addItem("No devices", None)
            self.device_box.setEnabled(False)
            self._update_start_enabled()
            self.statusBar().showMessage("Connect a device and press Refresh (USB debugging on).")
            return
        self.device_box.setEnabled(True)
        first_streamable = -1
        for i, dev in enumerate(devices):
            # Only streamable devices carry a serial as item data; others are
            # shown but can't be selected for streaming.
            self.device_box.addItem(dev.label, dev.serial if dev.streamable else None)
            if first_streamable < 0 and dev.streamable:
                first_streamable = i
        if first_streamable >= 0:
            self.device_box.setCurrentIndex(first_streamable)
        self._update_start_enabled()
        self.statusBar().showMessage(f"{len(devices)} device(s) found.")

    def _show_device_error(self, msg: str) -> None:
        self._devices = []
        self.device_box.clear()
        self.device_box.addItem("No devices", None)
        self.device_box.setEnabled(False)
        self._update_start_enabled()
        self.statusBar().showMessage(msg)

    def _current_serial(self) -> str | None:
        """The device we'd act on: the streaming reader's, else the picker's."""
        if self.reader and self.reader.isRunning():
            return self.reader.serial
        return self.device_box.currentData()

    def _update_start_enabled(self) -> None:
        streaming = self.reader is not None and self.reader.isRunning()
        streamable = bool(self._devices) and self.device_box.currentData() is not None
        self.start_btn.setEnabled(streamable and not streaming)
        self._update_package_enabled()

    def _update_package_enabled(self) -> None:
        enabled = self._current_serial() is not None
        for w in (self.package_box, self.load_pkgs_btn, self.apply_pkg_btn, self.clear_pkg_btn):
            w.setEnabled(enabled)

    # --- package / PID filter ----------------------------------------------
    def load_packages(self) -> None:
        serial = self._current_serial()
        if serial is None:
            return
        try:
            pkgs = list_packages(serial)
        except FileNotFoundError:
            self.statusBar().showMessage("adb not found.")
            return
        except Exception as exc:
            self.statusBar().showMessage(f"Could not list packages: {exc}")
            return
        current = self.package_box.currentText()
        self.package_box.clear()
        self.package_box.addItems(pkgs)
        self.package_box.setEditText(current)
        self.statusBar().showMessage(f"{len(pkgs)} packages loaded.")

    def apply_package_filter(self) -> None:
        serial = self._current_serial()
        package = self.package_box.currentText().strip()
        if serial is None or not package:
            return
        try:
            pids = resolve_pids(serial, package)
        except FileNotFoundError:
            self.statusBar().showMessage("adb not found.")
            return
        except Exception as exc:
            self.statusBar().showMessage(f"Could not resolve PIDs: {exc}")
            return
        if not pids:
            self.statusBar().showMessage(f"{package} isn't running — start it and apply again.")
            return
        self.proxy.set_pids(pids)
        self.statusBar().showMessage(f"Showing {package} (pid {', '.join(pids)}).")

    def clear_package_filter(self) -> None:
        self.proxy.set_pids(None)
        self.statusBar().showMessage("Package filter cleared.")

    def _apply_search(self) -> None:
        ok = self.proxy.set_search(self.search.text(), self.regex_check.isChecked())
        if ok:
            self.search.setStyleSheet("")
        else:
            # Invalid regex: keep the previous filter and flag the box. (This
            # tint would move into ui/theme.py once that exists.)
            self.search.setStyleSheet("QLineEdit { background-color: #ffd7d7; }")
            self.statusBar().showMessage("Invalid regex — showing previous match.")

    # --- save / load -------------------------------------------------------
    def save_log(self) -> None:
        default = f"zlog-{datetime.now():%Y%m%d-%H%M%S}.log"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Log", default, "Log files (*.log);;All files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(entries_to_text(self.model.all_entries()))
        except OSError as exc:
            self.statusBar().showMessage(f"Could not save: {exc}")
            return
        self.statusBar().showMessage(f"Saved {self.model.rowCount()} lines to {Path(path).name}.")

    def open_log(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Log", "", "Log files (*.log);;All files (*)"
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            self.statusBar().showMessage(f"Could not open: {exc}")
            return
        # Opening is an offline view: stop any live stream and drop the
        # device-specific package (PID) filter, which no longer applies.
        if self.reader and self.reader.isRunning():
            self.stop()
        self.proxy.set_pids(None)
        entries = text_to_entries(text)
        self.model.clear()
        self.model.append_entries(entries)
        self.statusBar().showMessage(f"Loaded {len(entries)} lines from {Path(path).name}.")

    # --- actions -----------------------------------------------------------
    def start(self) -> None:
        if self.reader and self.reader.isRunning():
            return
        serial = self.device_box.currentData()
        self.reader = AdbReader(serial=serial)
        self.reader.batch_ready.connect(self.on_batch)
        self.reader.error.connect(self.on_error)
        self.reader.start()
        # Lock device selection while streaming; switching needs Stop first.
        self.device_box.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._update_package_enabled()
        self.statusBar().showMessage(f"Streaming adb logcat ({serial or 'default'})…")

    def stop(self) -> None:
        if self.reader:
            self.reader.stop()
            self.reader = None
        self.refresh_btn.setEnabled(True)
        self.device_box.setEnabled(bool(self._devices))
        self.stop_btn.setEnabled(False)
        self._update_start_enabled()
        self.statusBar().showMessage("Stopped.")

    def on_batch(self, entries) -> None:
        at_bottom = self._is_scrolled_to_bottom()
        self.model.append_entries(entries)
        self.statusBar().showMessage(f"{self.model.rowCount()} lines")
        if at_bottom:
            self.table.scrollToBottom()

    def on_error(self, msg: str) -> None:
        self.statusBar().showMessage(msg)
        self.stop()

    def _is_scrolled_to_bottom(self) -> bool:
        bar = self.table.verticalScrollBar()
        return bar.value() >= bar.maximum() - 4

    def closeEvent(self, event) -> None:
        self.stop()
        super().closeEvent(event)
