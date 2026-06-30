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

from zlog.adb.reader import AdbReader
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

        # toolbar
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

        # connections
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.clear_btn.clicked.connect(self.model.clear)
        self.level_box.currentIndexChanged.connect(
            lambda: self.proxy.set_min_level(self.level_box.currentData())
        )
        self.search.textChanged.connect(self.proxy.set_text)

    # --- actions -----------------------------------------------------------
    def start(self) -> None:
        if self.reader and self.reader.isRunning():
            return
        self.reader = AdbReader()
        self.reader.batch_ready.connect(self.on_batch)
        self.reader.error.connect(self.on_error)
        self.reader.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.statusBar().showMessage("Streaming adb logcat…")

    def stop(self) -> None:
        if self.reader:
            self.reader.stop()
            self.reader = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
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
