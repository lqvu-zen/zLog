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

from PySide6.QtCore import QByteArray, QStandardPaths, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from zlog.adb.devices import list_devices
from zlog.adb.packages import list_packages, resolve_pids
from zlog.adb.reader import AdbReader
from zlog.core.devices import Device
from zlog.core.models import LogEntry
from zlog.core.proc import parse_proc_start
from zlog.core.session import entries_to_text, text_to_entries
from zlog.core.settings import load_settings, save_settings
from zlog.core.summary import format_level_summary
from zlog.ui.log_model import COLUMNS, MESSAGE_COL, LogFilterProxy, LogTableModel
from zlog.ui.table_view import LogTableView
from zlog.ui.theme import THEMES, build_stylesheet

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

        self.table = LogTableView()
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(MESSAGE_COL, QHeaderView.Stretch)
        # Fixed-ish initial widths for the narrow columns so Time fits on one line;
        # left Interactive (draggable) rather than ResizeToContents (which would
        # measure every row and hurt large logs). Message keeps stretching.
        for col, width in ((0, 145), (1, 60), (2, 60), (3, 55), (4, 170)):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
            self.table.setColumnWidth(col, width)
        self.table.setAlternatingRowColors(True)
        # Copy (Ctrl+C) and Select All: keyboard shortcuts via addAction, plus a
        # custom right-click menu that also offers per-tag highlighting.
        self.copy_action = QAction("Copy", self)
        self.copy_action.setShortcut(QKeySequence.Copy)
        self.copy_action.triggered.connect(self.copy_selection)
        self.select_all_action = QAction("Select All", self)
        self.select_all_action.triggered.connect(self.table.selectAll)
        self.table.addAction(self.copy_action)
        self.table.addAction(self.select_all_action)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_menu)

        # Detail pane: full, wrapped text of the selected row (read-only).
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("Select a line to see its full message here.")
        self.detail.setMaximumBlockCount(0)
        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.addWidget(self.table)
        self._splitter.addWidget(self.detail)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([520, 150])

        # --- row 1: device + stream controls ---
        self.device_box = QComboBox()
        self.device_box.setMinimumWidth(180)
        self.refresh_btn = QPushButton("Refresh")
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.clear_btn = QPushButton("Clear")
        self.follow_check = QCheckBox("Follow")
        self.follow_check.setChecked(True)
        self.stop_btn.setEnabled(False)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Device:"))
        row1.addWidget(self.device_box)
        row1.addWidget(self.refresh_btn)
        row1.addSpacing(16)
        row1.addWidget(self.start_btn)
        row1.addWidget(self.stop_btn)
        row1.addWidget(self.clear_btn)
        row1.addWidget(self.follow_check)
        row1.addStretch(1)

        # --- row 2: filters ---
        self.package_box = QComboBox()
        self.package_box.setEditable(True)
        self.package_box.setMinimumWidth(220)
        self.package_box.lineEdit().setPlaceholderText("Package, e.g. com.example.app")
        self.load_pkgs_btn = QPushButton("Load")
        self.apply_pkg_btn = QPushButton("Apply")
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
        layout.addWidget(self._splitter)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.setStatusBar(QStatusBar())
        self.count_label = QLabel("0 lines")
        self.statusBar().addPermanentWidget(self.count_label)

        # File menu: Open / Save log
        file_menu = self.menuBar().addMenu("&File")
        open_act = file_menu.addAction("&Open Log…")
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_log)
        save_act = file_menu.addAction("&Save Log…")
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_log)
        save_filtered_act = file_menu.addAction("Save &Filtered Log…")
        save_filtered_act.triggered.connect(self.save_filtered_log)

        # View menu: theme picker + details toggle
        view_menu = self.menuBar().addMenu("&View")
        theme_menu = view_menu.addMenu("&Theme")
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        for name in THEMES:
            act = theme_menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(name == "Light")
            self._theme_group.addAction(act)
            act.triggered.connect(lambda _checked=False, n=name: self.apply_theme(n))
        self._search_error_color = "#ffd7d7"

        self.details_action = view_menu.addAction("Show &Details")
        self.details_action.setCheckable(True)
        self.details_action.setChecked(True)
        self.details_action.toggled.connect(self.detail.setVisible)

        columns_menu = view_menu.addMenu("&Columns")
        self._column_actions = []
        for col, name in enumerate(COLUMNS):
            act = columns_menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(True)
            act.toggled.connect(lambda checked, c=col: self.table.setColumnHidden(c, not checked))
            self._column_actions.append(act)

        self.clear_on_start_action = view_menu.addAction("Clear on &Start")
        self.clear_on_start_action.setCheckable(True)
        self.clear_on_start_action.setChecked(False)

        self.reader: AdbReader | None = None
        self._devices: list[Device] = []
        self._filter_package: str | None = None
        self._filter_pids: set[str] = set()
        self._theme_name = "Light"

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
        self.table.selectionModel().currentChanged.connect(self._update_detail)
        self.model.rowsInserted.connect(self._update_counts)
        self.model.modelReset.connect(self._update_counts)
        self.proxy.layoutChanged.connect(self._update_placeholder)
        self.proxy.modelReset.connect(self._update_placeholder)
        self.proxy.rowsInserted.connect(self._update_placeholder)
        self.proxy.rowsRemoved.connect(self._update_placeholder)

        # initial device scan
        self.refresh_devices()

        # restore saved settings (theme, geometry, filters, highlights); falls
        # back to defaults on first run.
        self._load_and_apply_settings()

        self._update_placeholder()

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
        self._filter_package = package
        self._filter_pids = set(pids)
        self.proxy.set_pids(self._filter_pids)
        self.statusBar().showMessage(f"Showing {package} (pid {', '.join(pids)}).")

    def clear_package_filter(self) -> None:
        self._filter_package = None
        self._filter_pids = set()
        self.proxy.set_pids(None)
        self.statusBar().showMessage("Package filter cleared.")

    def _apply_search(self) -> None:
        ok = self.proxy.set_search(self.search.text(), self.regex_check.isChecked())
        if ok:
            self.search.setStyleSheet("")
        else:
            # Invalid regex: keep the previous filter and flag the box. (This
            # tint would move into ui/theme.py once that exists.)
            self.search.setStyleSheet(
                f"QLineEdit {{ background-color: {self._search_error_color}; }}"
            )
            self.statusBar().showMessage("Invalid regex — showing previous match.")

    # --- theme -------------------------------------------------------------
    def apply_theme(self, name: str) -> None:
        self._theme_name = name
        theme = THEMES[name]
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet(theme))
        self.model.set_level_colors(theme.level_colors)
        self._search_error_color = theme.search_error
        self.table.viewport().update()  # repaint existing rows with new tints
        self._apply_search()  # re-tint the search box under the new theme

    def _update_placeholder(self) -> None:
        """Contextual empty-state text: nothing captured vs. filtered to nothing."""
        if self.model.rowCount() == 0:
            text = (
                "No logs yet — pick a device and press Start,\nor open a saved log (File → Open)."
            )
        elif self.proxy.rowCount() == 0:
            text = "No lines match the current filters."
        else:
            text = ""
        self.table.set_placeholder(text)

    # --- copy / selection --------------------------------------------------
    def _selected_entries(self) -> list[LogEntry]:
        """The entries for the selected rows, in top-to-bottom order, mapped from
        the proxy (what's visible) back to the source model."""
        rows = self.table.selectionModel().selectedRows()
        source_rows = sorted(self.proxy.mapToSource(index).row() for index in rows)
        return [self.model.entry_at(row) for row in source_rows]

    def _selected_text(self) -> str:
        return entries_to_text(self._selected_entries())

    def copy_selection(self) -> None:
        text = self._selected_text()
        if not text:
            return
        QApplication.clipboard().setText(text)
        n = text.count("\n")
        self.statusBar().showMessage(f"Copied {n} line{'s' if n != 1 else ''}.")

    def _show_table_menu(self, pos) -> None:
        menu = QMenu(self.table)
        menu.addAction(self.copy_action)
        menu.addAction(self.select_all_action)
        menu.addSeparator()
        index = self.table.indexAt(pos)
        tag = ""
        if index.isValid():
            tag = self.model.entry_at(self.proxy.mapToSource(index).row()).tag
        highlight = menu.addAction(f"Highlight tag \u201c{tag}\u201d…" if tag else "Highlight tag…")
        highlight.setEnabled(bool(tag))
        highlight.triggered.connect(lambda: self._highlight_tag(tag))
        clear = menu.addAction("Clear tag highlights")
        clear.triggered.connect(self._clear_tag_highlights)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _highlight_tag(self, tag: str) -> None:
        if not tag:
            return
        color = QColorDialog.getColor(parent=self, title=f"Highlight color for {tag}")
        if color.isValid():
            self.model.set_tag_color(tag, color.name())
            self.table.viewport().update()
            self.statusBar().showMessage(f"Highlighting tag \u201c{tag}\u201d.")

    def _clear_tag_highlights(self) -> None:
        self.model.clear_tag_colors()
        self.table.viewport().update()
        self.statusBar().showMessage("Cleared tag highlights.")

    # --- save / load -------------------------------------------------------
    def _filtered_entries(self) -> list[LogEntry]:
        """The entries currently visible through the proxy (in order)."""
        return [
            self.model.entry_at(self.proxy.mapToSource(self.proxy.index(row, 0)).row())
            for row in range(self.proxy.rowCount())
        ]

    def _write_log(self, entries: list[LogEntry], default_name: str) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Log", default_name, "Log files (*.log);;All files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(entries_to_text(entries))
        except OSError as exc:
            self.statusBar().showMessage(f"Could not save: {exc}")
            return
        self.statusBar().showMessage(f"Saved {len(entries)} lines to {Path(path).name}.")

    def save_log(self) -> None:
        stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
        self._write_log(self.model.all_entries(), f"zlog-{stamp}.log")

    def save_filtered_log(self) -> None:
        stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
        self._write_log(self._filtered_entries(), f"zlog-{stamp}-filtered.log")

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

    # --- status counts -----------------------------------------------------
    def _update_counts(self, *args) -> None:
        self.count_label.setText(
            format_level_summary(self.model.rowCount(), self.model.level_counts())
        )

    # --- detail pane -------------------------------------------------------
    def _update_detail(self, current, previous=None) -> None:
        if current is None or not current.isValid():
            self.detail.clear()
            return
        entry = self.model.entry_at(self.proxy.mapToSource(current).row())
        dash = "\u2014"
        header = (
            f"Time  {entry.time or dash}    "
            f"PID {entry.pid or dash}  TID {entry.tid or dash}    "
            f"{entry.level or dash}  {entry.tag or dash}"
        )
        self.detail.setPlainText(header + "\n\n" + entry.message)

    # --- settings ----------------------------------------------------------
    def _settings_path(self) -> Path:
        base = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation) or str(
            Path.home() / ".zlog"
        )
        return Path(base) / "settings.json"

    def _load_and_apply_settings(self) -> None:
        data = load_settings(str(self._settings_path()))
        geometry = data.get("geometry") or ""
        if geometry:
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode("ascii")))
        theme = data.get("theme", "Light")
        if theme not in THEMES:
            theme = "Light"
        for act in self._theme_group.actions():
            act.setChecked(act.text() == theme)
        self.apply_theme(theme)
        self.follow_check.setChecked(bool(data.get("follow", True)))
        idx = self.level_box.findData(data.get("min_level", "V"))
        if idx >= 0:
            self.level_box.setCurrentIndex(idx)
        self.regex_check.setChecked(bool(data.get("regex", False)))
        self.details_action.setChecked(bool(data.get("show_details", True)))
        self.detail.setVisible(self.details_action.isChecked())
        self.clear_on_start_action.setChecked(bool(data.get("clear_on_start", False)))
        hidden = data.get("hidden_columns") or []
        if isinstance(hidden, list):
            for col, act in enumerate(self._column_actions):
                visible = col not in hidden
                act.setChecked(visible)
                self.table.setColumnHidden(col, not visible)
        highlights = data.get("tag_highlights") or {}
        if isinstance(highlights, dict):
            for tag, color in highlights.items():
                self.model.set_tag_color(str(tag), str(color))
        self.table.viewport().update()

    def _save_settings(self) -> None:
        data = {
            "geometry": bytes(self.saveGeometry().toBase64()).decode("ascii"),
            "theme": self._theme_name,
            "follow": self.follow_check.isChecked(),
            "min_level": self.level_box.currentData(),
            "regex": self.regex_check.isChecked(),
            "tag_highlights": self.model.tag_colors(),
            "show_details": self.details_action.isChecked(),
            "hidden_columns": [
                c for c in range(len(self._column_actions)) if self.table.isColumnHidden(c)
            ],
            "clear_on_start": self.clear_on_start_action.isChecked(),
        }
        try:
            save_settings(str(self._settings_path()), data)
        except OSError:
            pass  # never let a settings write failure break shutdown

    # --- actions -----------------------------------------------------------
    def start(self) -> None:
        if self.reader and self.reader.isRunning():
            return
        if self.clear_on_start_action.isChecked():
            self.model.clear()
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
        self.model.append_entries(entries)
        if self._filter_package is not None:
            self._track_new_pids(entries)
        if self.follow_check.isChecked():
            self.table.scrollToBottom()

    def _track_new_pids(self, entries) -> None:
        """Keep an active package filter live: add PIDs of newly started
        processes of the filtered package (so a restart keeps showing)."""
        added = False
        for entry in entries:
            result = parse_proc_start(entry.message)
            if result is None:
                continue
            pid, package = result
            if package == self._filter_package and pid not in self._filter_pids:
                self._filter_pids.add(pid)
                added = True
        if added:
            self.proxy.set_pids(self._filter_pids)
            pids = ", ".join(sorted(self._filter_pids))
            self.statusBar().showMessage(f"{self._filter_package} restarted → tracking pid {pids}.")

    def on_error(self, msg: str) -> None:
        self.statusBar().showMessage(msg)
        self.stop()

    def closeEvent(self, event) -> None:
        self._save_settings()
        self.stop()
        super().closeEvent(event)
