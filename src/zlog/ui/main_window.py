"""The main window: wires the reader, model, filters and table together.

Data flow:

    AdbReader (thread) --batch_ready--> LogTableModel (master list)
                                              |
                                        LogFilterProxy (level + text)
                                              |
                                         QTableView (what you see)
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
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
from zlog.adb.reader import AdbReader
from zlog.core.devices import Device
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

        # device picker
        self.device_box = QComboBox()
        self.device_box.setMinimumWidth(180)
        self.refresh_btn = QPushButton("Refresh")

        # stream controls
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.clear_btn = QPushButton("Clear")
        self.stop_btn.setEnabled(False)

        self.level_box = QComboBox()
        for letter in LEVELS:
            self.level_box.addItem(letter, letter)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by tag or message…")

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Device:"))
        toolbar.addWidget(self.device_box)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addSpacing(16)
        toolbar.addWidget(self.start_btn)
        toolbar.addWidget(self.stop_btn)
        toolbar.addWidget(self.clear_btn)
        toolbar.addSpacing(16)
        toolbar.addWidget(QLabel("Min level:"))
        toolbar.addWidget(self.level_box)
        toolbar.addWidget(self.search, stretch=1)

        layout = QVBoxLayout()
        layout.addLayout(toolbar)
        layout.addWidget(self.table)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.setStatusBar(QStatusBar())

        self.reader: AdbReader | None = None
        self._devices: list[Device] = []

        # connections
        self.refresh_btn.clicked.connect(self.refresh_devices)
        self.device_box.currentIndexChanged.connect(self._update_start_enabled)
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.clear_btn.clicked.connect(self.model.clear)
        self.level_box.currentIndexChanged.connect(
            lambda: self.proxy.set_min_level(self.level_box.currentData())
        )
        self.search.textChanged.connect(self.proxy.set_text)

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

    def _update_start_enabled(self) -> None:
        streaming = self.reader is not None and self.reader.isRunning()
        streamable = bool(self._devices) and self.device_box.currentData() is not None
        self.start_btn.setEnabled(streamable and not streaming)

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
