"""The main window: wires the reader, model, filters and table together.

Data flow:

    AdbReader (thread) --batch_ready--> LogTableModel (master list)
                                              |
                                        LogFilterProxy (level + text + package PIDs)
                                              |
                                         QTableView (what you see)
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, QEvent, QStandardPaths, QStringListModel, Qt
from PySide6.QtGui import QAction, QActionGroup, QFont, QFontMetrics, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QCompleter,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
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
from zlog.adb.packages import clear_logcat, list_packages, resolve_pids
from zlog.adb.reader import AdbReader
from zlog.core.devices import Device
from zlog.core.history import normalize_history, push_history
from zlog.core.models import LogEntry
from zlog.core.presets import make_preset, normalize_presets, remove_preset, upsert_preset
from zlog.core.query import parse_query
from zlog.core.search import compile_matcher
from zlog.core.session import entries_to_text, text_to_entries
from zlog.core.settings import DEFAULTS, load_settings, save_settings
from zlog.core.summary import format_level_summary
from zlog.ui.device_controller import DeviceController
from zlog.ui.log_delegate import LogItemDelegate
from zlog.ui.log_model import COLUMNS, LogFilterProxy, LogTableModel
from zlog.ui.table_view import LogTableView
from zlog.ui.theme import THEMES, build_stylesheet

LEVELS = ["V", "D", "I", "W", "E", "F"]
LEVEL_NAMES = {"V": "Verbose", "D": "Debug", "I": "Info", "W": "Warn", "E": "Error", "F": "Fatal"}

# Preferred monospace faces for the log, first available wins (Consolas on
# Windows, DejaVu Sans Mono on Linux); Courier New + the Monospace style hint
# are the safe last resort. "monospace" alone falls back to a thin, hard-to-read
# face on Windows.
LOG_FONT_FAMILIES = [
    "Consolas",
    "Cascadia Mono",
    "SF Mono",
    "Menlo",
    "DejaVu Sans Mono",
    "Courier New",
]
BASE_FONT_PT = 11  # readable default; the zoom offset (font_delta) adjusts it


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("zLog — Android Log Viewer")
        self.resize(1100, 700)

        # Runtime state, created before widgets so slots can rely on it existing.
        self.reader: AdbReader | None = None
        self.devctl = DeviceController(self)  # device picker + package/PID filter state
        self._theme_name = "Light"
        self._presets: list[dict] = []  # saved filter presets
        self._font_delta = 0  # point-size offset for the table + detail pane
        self._query_package = ""  # last package resolved from the query bar
        self._history: list[str] = []  # recent query-bar entries
        self._search_error_color = THEMES["Light"].search_error  # apply_theme overrides per theme

        self._build_widgets()
        self._build_layout()
        self._build_menus()
        self._connect_signals()

        # Populate the picker, then restore saved settings over defaults (the
        # last-used device is reselected in _load_and_apply_settings, after this).
        self.refresh_devices()
        self._load_and_apply_settings()
        self._update_placeholder()

    # --- construction (called once, in order, from __init__) ---------------
    def _build_widgets(self) -> None:
        """Create the model/proxy/view and every toolbar widget (no layout yet)."""
        self.model = LogTableModel(self)
        self.proxy = LogFilterProxy(self)
        self.proxy.setSourceModel(self.model)

        self.table = LogTableView()
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        # Android-Studio-style dense view: one line per entry. Show only column 0
        # stretched full-width and paint the whole entry with a delegate (the model
        # stays virtualized — the delegate runs only for visible rows).
        mono = QFont()
        mono.setFamilies(LOG_FONT_FAMILIES)
        mono.setStyleHint(QFont.Monospace)
        mono.setFixedPitch(True)
        self.table.setFont(mono)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, len(COLUMNS)):
            self.table.setColumnHidden(col, True)
        self.log_delegate = LogItemDelegate(self)
        self.table.setItemDelegateForColumn(0, self.log_delegate)
        # Copy (Ctrl+C) and Select All: keyboard shortcuts via addAction, plus a
        # custom right-click menu that also offers per-tag highlighting.
        self.copy_action = QAction("Copy", self)
        self.copy_action.setShortcut(QKeySequence.Copy)
        self.copy_action.triggered.connect(self.copy_selection)
        self.select_all_action = QAction("Select All", self)
        self.select_all_action.triggered.connect(self.table.selectAll)
        self.bookmark_action = QAction("Toggle Bookmark", self)
        self.bookmark_action.setShortcut("Ctrl+B")
        self.bookmark_action.triggered.connect(self._toggle_bookmark)
        self.table.addAction(self.copy_action)
        self.table.addAction(self.select_all_action)
        self.table.addAction(self.bookmark_action)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_menu)

        # Detail pane: full, wrapped text of the selected row (read-only).
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("Select a line to see its full message here.")
        self.detail.setMaximumBlockCount(0)

        # Row 1: device + stream controls.
        self.device_box = QComboBox()
        self.device_box.setMinimumWidth(180)
        self.refresh_btn = QPushButton("Refresh")
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.clear_btn = QPushButton("Clear")
        self.clear_device_btn = QPushButton("Clear device")
        self.clear_device_btn.setToolTip("Wipe the device's logcat buffer (adb logcat -c)")
        self.follow_check = QCheckBox("Follow")
        self.follow_check.setChecked(True)
        self.to_top_btn = QPushButton("Top")
        self.to_top_btn.setToolTip("Scroll to the oldest line")
        self.to_latest_btn = QPushButton("Latest")
        self.to_latest_btn.setToolTip("Scroll to the newest line")
        self.stop_btn.setEnabled(False)

        # Row 2: filters.
        self.package_box = QComboBox()
        self.package_box.setEditable(True)
        self.package_box.setMinimumWidth(220)
        self.package_box.lineEdit().setPlaceholderText("Package, e.g. com.example.app")
        self.load_pkgs_btn = QPushButton("Load")
        self.apply_pkg_btn = QPushButton("Apply")
        self.clear_pkg_btn = QPushButton("Clear pkg")

        self.level_box = QComboBox()
        for letter in LEVELS:
            self.level_box.addItem(LEVEL_NAMES[letter], letter)  # text = name, data = letter
        self.level_box.setToolTip(
            "Minimum log level (V \u2264 D \u2264 I \u2264 W \u2264 E \u2264 F)"
        )

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by tag or message…")
        self.exclude = QLineEdit()
        self.exclude.setPlaceholderText("Exclude…")
        self.exclude.setToolTip("Hide lines matching this term (uses the Regex/Case toggles)")
        self.exclude.setMinimumWidth(150)
        self.match_prev_btn = QPushButton("<")
        self.match_prev_btn.setMaximumWidth(28)
        self.match_prev_btn.setToolTip("Previous match (Shift+F3)")
        self.match_next_btn = QPushButton(">")
        self.match_next_btn.setMaximumWidth(28)
        self.match_next_btn.setToolTip("Next match (F3)")
        self.match_label = QLabel("")
        self.match_label.setMinimumWidth(64)
        self.regex_check = QCheckBox("Regex")
        self.case_check = QCheckBox("Case")
        self.case_check.setToolTip("Match the search case-sensitively")
        self.search_mode_box = QComboBox()
        self.search_mode_box.addItem("Filter", "filter")
        self.search_mode_box.addItem("Highlight", "highlight")
        self.search_mode_box.setToolTip("Filter hides non-matches; Highlight tints matches")
        self.clear_filters_btn = QPushButton("Clear filters")
        self.clear_filters_btn.setToolTip("Reset level, search, and package filters")

        self.count_label = QLabel("0 lines")

        # Single query bar, parsed into the filters.
        self.query = QLineEdit()
        self.query.setPlaceholderText(
            "Filter — e.g. level:E tag:Activity package:com.x -noise text"
        )
        self.query.setClearButtonEnabled(True)
        self._history_model = QStringListModel(self)
        completer = QCompleter(self._history_model, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.query.setCompleter(completer)

    def _build_layout(self) -> None:
        """Arrange the widgets built in _build_widgets into the window."""
        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.addWidget(self.table)
        self._splitter.addWidget(self.detail)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([520, 150])

        # Compact glyph buttons for the stream/device actions.
        for btn, glyph, tip in (
            (self.refresh_btn, "\u21bb", "Refresh devices"),
            (self.start_btn, "\u25b6", "Start streaming"),
            (self.stop_btn, "\u25a0", "Stop streaming"),
            (self.clear_btn, "\u2715", "Clear the log view"),
            (self.to_top_btn, "\u2912", "Scroll to the oldest line"),
            (self.to_latest_btn, "\u2913", "Scroll to the newest line"),
        ):
            btn.setText(glyph)
            btn.setToolTip(tip)
            btn.setFixedWidth(34)

        # Control bar: device/stream controls and package controls on one row,
        # split by a vertical divider (there's room, and it saves a stacked row).
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Device:"))
        top_row.addWidget(self.device_box)
        top_row.addWidget(self.refresh_btn)
        top_row.addSpacing(12)
        top_row.addWidget(self.start_btn)
        top_row.addWidget(self.stop_btn)
        top_row.addWidget(self.clear_btn)
        top_row.addWidget(self.clear_device_btn)
        top_row.addWidget(self.follow_check)
        top_row.addSpacing(12)
        top_row.addWidget(self.to_top_btn)
        top_row.addWidget(self.to_latest_btn)
        top_row.addSpacing(12)
        top_row.addWidget(self._vsep())
        top_row.addSpacing(12)
        top_row.addWidget(QLabel("Package:"))
        top_row.addWidget(self.package_box)
        top_row.addWidget(self.load_pkgs_btn)
        top_row.addWidget(self.apply_pkg_btn)
        top_row.addWidget(self.clear_pkg_btn)
        top_row.addSpacing(12)
        top_row.addWidget(self._vsep())
        top_row.addSpacing(12)
        top_row.addWidget(QLabel("Level:"))
        top_row.addWidget(self.level_box)
        top_row.addStretch(1)

        # Filter bar: the query box on its own full-width row.
        filter_row = QHBoxLayout()
        filter_row.addWidget(self.query)

        layout = QVBoxLayout()
        layout.addLayout(top_row)
        layout.addLayout(filter_row)
        layout.addWidget(self._splitter)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.setStatusBar(QStatusBar())
        self.statusBar().addPermanentWidget(self.count_label)

    def _vsep(self) -> QFrame:
        """A thin vertical separator that visually groups related toolbar controls."""
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def _build_menus(self) -> None:
        """Build the File and View menus (their actions wire themselves here)."""
        file_menu = self.menuBar().addMenu("&File")
        open_act = file_menu.addAction("&Open Log…")
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_log)
        save_act = file_menu.addAction("&Save Log…")
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_log)
        save_filtered_act = file_menu.addAction("Save &Filtered Log…")
        save_filtered_act.triggered.connect(self.save_filtered_log)

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

        self.details_action = view_menu.addAction("Show &Details")
        self.details_action.setCheckable(True)
        self.details_action.setChecked(True)
        self.details_action.toggled.connect(self.detail.setVisible)

        self.clear_on_start_action = view_menu.addAction("Clear on &Start")
        self.clear_on_start_action.setCheckable(True)
        self.clear_on_start_action.setChecked(False)

        clear_filters_act = view_menu.addAction("Clear F&ilters")
        clear_filters_act.triggered.connect(self.clear_filters)

        search_menu = view_menu.addMenu("&Search options")
        self.case_action = search_menu.addAction("Case sensitive")
        self.case_action.setCheckable(True)
        self.case_action.toggled.connect(self._on_case_toggled)
        self.highlight_action = search_menu.addAction("Highlight matches (don't hide)")
        self.highlight_action.setCheckable(True)
        self.highlight_action.toggled.connect(self._on_highlight_toggled)

        self.presets_menu = view_menu.addMenu("Filter &Presets")
        self._rebuild_presets_menu()

        time_menu = view_menu.addMenu("&Time display")
        self._time_group = QActionGroup(self)
        self._time_group.setExclusive(True)
        self._time_actions = {}
        time_modes = (("absolute", "Absolute"), ("since_start", "Since start"), ("delta", "Delta"))
        for mode, label in time_modes:
            act = time_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(mode == "absolute")
            self._time_group.addAction(act)
            act.triggered.connect(lambda _c=False, m=mode: self.model.set_time_mode(m))
            self._time_actions[mode] = act

        view_menu.addSeparator()
        next_bm = view_menu.addAction("Next Bookmark")
        next_bm.setShortcut("F2")
        next_bm.triggered.connect(lambda: self._goto_bookmark(1))
        prev_bm = view_menu.addAction("Previous Bookmark")
        prev_bm.setShortcut("Shift+F2")
        prev_bm.triggered.connect(lambda: self._goto_bookmark(-1))
        clear_bm = view_menu.addAction("Clear Bookmarks")
        clear_bm.triggered.connect(self._clear_bookmarks)

        view_menu.addSeparator()
        zoom_in = view_menu.addAction("Zoom In")
        zoom_in.setShortcut("Ctrl+=")
        zoom_in.triggered.connect(lambda: self._zoom(1))
        zoom_out = view_menu.addAction("Zoom Out")
        zoom_out.setShortcut("Ctrl+-")
        zoom_out.triggered.connect(lambda: self._zoom(-1))
        zoom_reset = view_menu.addAction("Reset Zoom")
        zoom_reset.setShortcut("Ctrl+0")
        zoom_reset.triggered.connect(self._reset_zoom)

        buffers_menu = view_menu.addMenu("Log &buffers")
        self._buffer_actions = {}
        for name in ("main", "system", "crash", "radio", "events", "kernel"):
            act = buffers_menu.addAction(name)
            act.setCheckable(True)
            self._buffer_actions[name] = act
        buffers_menu.addSeparator()
        buffers_hint = buffers_menu.addAction("(applies on next Start)")
        buffers_hint.setEnabled(False)

        clear_buf_act = view_menu.addAction("Clear device log &buffer")
        clear_buf_act.triggered.connect(self._clear_device_buffer)

        tail_menu = view_menu.addMenu("&Start from")
        self._tail_group = QActionGroup(self)
        self._tail_group.setExclusive(True)
        self._tail_actions = {}
        for count, label in (
            (0, "Whole buffer"),
            (500, "Last 500"),
            (1000, "Last 1000"),
            (5000, "Last 5000"),
        ):
            act = tail_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(count == 0)
            self._tail_group.addAction(act)
            self._tail_actions[count] = act

        cap_menu = view_menu.addMenu("Buffer &limit")
        self._max_rows_group = QActionGroup(self)
        self._max_rows_group.setExclusive(True)
        self._max_rows_actions = {}
        for cap, label in (
            (0, "Unlimited"),
            (10000, "10,000 lines"),
            (50000, "50,000 lines"),
            (100000, "100,000 lines"),
        ):
            act = cap_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(cap == 0)
            act.triggered.connect(lambda _checked=False, n=cap: self.model.set_max_rows(n))
            self._max_rows_group.addAction(act)
            self._max_rows_actions[cap] = act

    def _connect_signals(self) -> None:
        """Wire toolbar/model/proxy signals to their slots (menu actions wire
        themselves in _build_menus)."""
        self.refresh_btn.clicked.connect(self.refresh_devices)
        self.to_top_btn.clicked.connect(self.table.scrollToTop)
        self.to_latest_btn.clicked.connect(self.table.scrollToBottom)
        self.device_box.currentIndexChanged.connect(self._update_start_enabled)
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.clear_btn.clicked.connect(self.model.clear)
        self.clear_device_btn.clicked.connect(self._clear_device_buffer)
        # Ctrl+wheel over the log or detail zooms (handled in eventFilter);
        # filter the viewports, since that is where wheel events are delivered.
        self.table.viewport().installEventFilter(self)
        self.detail.viewport().installEventFilter(self)
        self.load_pkgs_btn.clicked.connect(self.load_packages)
        self.apply_pkg_btn.clicked.connect(self.apply_package_filter)
        self.clear_pkg_btn.clicked.connect(self.clear_package_filter)
        self.package_box.lineEdit().returnPressed.connect(self.apply_package_filter)
        self.level_box.currentIndexChanged.connect(
            lambda: self.proxy.set_min_level(self.level_box.currentData())
        )
        self.search.textChanged.connect(self._apply_search)
        self.query.textChanged.connect(self._apply_query)
        self.query.returnPressed.connect(self._commit_query_history)
        self.exclude.textChanged.connect(self._apply_search)
        self.match_next_btn.clicked.connect(lambda: self._goto_match(1))
        self.match_prev_btn.clicked.connect(lambda: self._goto_match(-1))
        QShortcut(QKeySequence("F3"), self, activated=lambda: self._goto_match(1))
        QShortcut(QKeySequence("Shift+F3"), self, activated=lambda: self._goto_match(-1))
        self.regex_check.toggled.connect(self._apply_search)
        self.case_check.toggled.connect(self._apply_search)
        self.search_mode_box.currentIndexChanged.connect(self._apply_search)
        self.clear_filters_btn.clicked.connect(self.clear_filters)
        self.table.selectionModel().currentChanged.connect(self._update_detail)
        self.model.rowsInserted.connect(self._update_counts)
        self.model.modelReset.connect(self._update_counts)
        self.proxy.layoutChanged.connect(self._update_placeholder)
        self.proxy.modelReset.connect(self._update_placeholder)
        self.proxy.rowsInserted.connect(self._update_placeholder)
        self.proxy.rowsRemoved.connect(self._update_placeholder)
        self.proxy.layoutChanged.connect(self._update_counts)
        self.proxy.rowsRemoved.connect(self._update_counts)

    # --- devices -----------------------------------------------------------
    def _run_adb(self, fn, *, missing_msg, error_prefix, report):
        """Run an adb-backed call, routing a missing `adb` and any other failure
        through `report`. Returns the call's result, or None on failure."""
        try:
            return fn()
        except FileNotFoundError:
            report(missing_msg)
        except Exception as exc:  # timeout or other adb failure
            report(f"{error_prefix}: {exc}")
        return None

    def refresh_devices(self) -> None:
        devices = self._run_adb(
            list_devices,
            missing_msg="adb not found — install Android platform-tools and add it to PATH.",
            error_prefix="Could not list devices",
            report=self._show_device_error,
        )
        if devices is None:
            return
        self._populate_devices(devices)

    def _populate_devices(self, devices: list[Device]) -> None:
        """Fill the picker from a device list (also called by the run-zlog driver
        with fake devices, so it stays free of subprocess calls)."""
        self.devctl.set_devices(devices)
        self.device_box.clear()
        if not devices:
            self.device_box.addItem("No devices", None)
            self.device_box.setEnabled(False)
            self._update_start_enabled()
            self.statusBar().showMessage("Connect a device and press Refresh (USB debugging on).")
            return
        self.device_box.setEnabled(True)
        for dev in devices:
            # Only streamable devices carry a serial as item data; others are
            # shown but can't be selected for streaming.
            self.device_box.addItem(dev.label, dev.serial if dev.streamable else None)
        chosen = self.devctl.choose_index()  # prefers the last-used device
        if chosen >= 0:
            self.device_box.setCurrentIndex(chosen)
            self.devctl.remember(self.device_box.itemData(chosen))
        self._update_start_enabled()
        self.statusBar().showMessage(f"{len(devices)} device(s) found.")

    def _show_device_error(self, msg: str) -> None:
        self.devctl.set_devices([])
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
        streamable = bool(self.devctl.devices) and self.device_box.currentData() is not None
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
        pkgs = self._run_adb(
            lambda: list_packages(serial),
            missing_msg="adb not found.",
            error_prefix="Could not list packages",
            report=self.statusBar().showMessage,
        )
        if pkgs is None:
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
        pids = self._run_adb(
            lambda: resolve_pids(serial, package),
            missing_msg="adb not found.",
            error_prefix="Could not resolve PIDs",
            report=self.statusBar().showMessage,
        )
        if pids is None:
            return
        if not pids:
            self.statusBar().showMessage(f"{package} isn't running — start it and apply again.")
            return
        self.devctl.apply_filter(package, pids)
        self.proxy.set_pids(self.devctl.filter_pids)
        self.statusBar().showMessage(f"Showing {package} (pid {', '.join(pids)}).")

    def clear_package_filter(self) -> None:
        self.devctl.clear_filter()
        self.proxy.set_pids(None)
        self.statusBar().showMessage("Package filter cleared.")

    def clear_filters(self) -> None:
        """Reset every filter to 'show everything' without touching the log."""
        idx = self.level_box.findData("V")
        if idx >= 0:
            self.level_box.setCurrentIndex(idx)  # min level back to V (show all)
        self.query.clear()  # fires _apply_query -> resets tag/search/exclude/pkg
        self.statusBar().showMessage("Filters cleared.")

    # --- filter presets ----------------------------------------------------
    def _rebuild_presets_menu(self) -> None:
        """Repopulate the Presets submenu from self._presets (called on load and
        after every save/delete)."""
        self.presets_menu.clear()
        save_act = self.presets_menu.addAction("Save current filter as…")
        save_act.triggered.connect(self.save_current_preset)
        if self._presets:
            self.presets_menu.addSeparator()
            for preset in self._presets:
                act = self.presets_menu.addAction(preset["name"])
                act.triggered.connect(lambda _checked=False, p=preset: self._apply_preset(p))
            delete_menu = self.presets_menu.addMenu("Delete")
            for preset in self._presets:
                act = delete_menu.addAction(preset["name"])
                act.triggered.connect(
                    lambda _checked=False, n=preset["name"]: self._delete_preset(n)
                )

    def save_current_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Filter Preset", "Preset name:")
        name = name.strip()
        if not ok or not name:
            return
        preset = make_preset(
            name,
            min_level=self.level_box.currentData(),
            search=self.search.text(),
            regex=self.regex_check.isChecked(),
            case=self.case_check.isChecked(),
            package=self.package_box.currentText().strip(),
        )
        self._presets = upsert_preset(self._presets, preset)
        self._rebuild_presets_menu()
        self._save_settings()
        self.statusBar().showMessage(f"Saved preset {name!r}.")

    def _apply_preset(self, preset: dict) -> None:
        self.case_check.setChecked(bool(preset.get("case")))
        parts = []
        level = preset.get("min_level", "V")
        if level and level != "V":
            parts.append(f"level:{level}")
        package = preset.get("package", "")
        if package:
            parts.append(f"package:{package}")
        search = preset.get("search", "")
        if search:
            parts.append(f"/{search}/" if preset.get("regex") else search)
        self.query.setText(" ".join(parts))  # -> _apply_query
        self.statusBar().showMessage(f"Applied preset {preset.get('name', '')!r}.")

    def _delete_preset(self, name: str) -> None:
        self._presets = remove_preset(self._presets, name)
        self._rebuild_presets_menu()
        self._save_settings()
        self.statusBar().showMessage(f"Deleted preset {name!r}.")

    def _apply_search(self) -> None:
        text = self.search.text()
        regex = self.regex_check.isChecked()
        case = self.case_check.isChecked()
        if self.search_mode_box.currentData() == "highlight":
            # Highlight mode: show every row, tint the matches in the model.
            self.proxy.set_search("", regex, case)
            ok = self.model.set_highlight(text, regex, case)
        else:
            # Filter mode: hide non-matches, clear any highlight.
            self.model.set_highlight("", regex, case)
            ok = self.proxy.set_search(text, regex, case)
        if ok:
            self.search.setStyleSheet("")
        else:
            # Invalid regex: keep the previous filter and flag the box with the
            # active theme's error tint.
            self.search.setStyleSheet(
                f"QLineEdit {{ background-color: {self._search_error_color}; }}"
            )
            self.statusBar().showMessage("Invalid regex — showing previous match.")
        self._update_match_label()

    def _apply_query(self) -> None:
        """Parse the single query bar and drive the (hidden) filter widgets +
        proxy gates. This is the one place filtering is applied in the new UI."""
        spec = parse_query(self.query.text())
        case = self.case_check.isChecked()
        if spec.levels:
            self.proxy.set_levels(set(spec.levels))  # exact level set
        else:
            self.proxy.set_levels(None)
            if spec.level:
                idx = self.level_box.findData(spec.level)
                if idx >= 0:
                    self.level_box.setCurrentIndex(idx)  # query level: drives the dropdown
            else:
                # No level: token — the visible Level dropdown is the floor source.
                self.proxy.set_min_level(self.level_box.currentData())
        self.proxy.set_tag(spec.tag)
        ex_pat = "|".join(re.escape(t) for t in spec.excludes)
        ex_ok = self.proxy.set_exclude(ex_pat, bool(spec.excludes), case)
        self.regex_check.setChecked(spec.regex)  # -> _apply_search
        self.search.setText(spec.search)  # -> _apply_search (search + highlight)
        search_ok = True
        try:
            compile_matcher(spec.search, spec.regex, case)
        except re.error:
            search_ok = False
        good = search_ok and ex_ok
        self.query.setStyleSheet(
            "" if good else f"QLineEdit {{ background-color: {self._search_error_color}; }}"
        )
        if spec.package != self._query_package:
            self._query_package = spec.package
            self.package_box.setEditText(spec.package)
            if spec.package:
                self.apply_package_filter()
            else:
                self.clear_package_filter()

    def _commit_query_history(self) -> None:
        """Remember the current query (on Enter) for the completer; persist it."""
        text = self.query.text().strip()
        if not text:
            return
        self._history = push_history(self._history, text)
        self._history_model.setStringList(self._history)
        self._save_settings()

    def _on_case_toggled(self, checked: bool) -> None:
        self.case_check.setChecked(checked)
        self._apply_query()

    def _on_highlight_toggled(self, checked: bool) -> None:
        self.search_mode_box.setCurrentIndex(1 if checked else 0)
        self._apply_query()

    # --- match navigation --------------------------------------------------
    def _match_rows(self) -> list[int]:
        """Visible proxy rows whose tag+message match the current search term."""
        text = self.search.text()
        if not text:
            return []
        try:
            matcher = compile_matcher(
                text, self.regex_check.isChecked(), self.case_check.isChecked()
            )
        except re.error:
            return []
        rows = []
        for r in range(self.proxy.rowCount()):
            src = self.proxy.mapToSource(self.proxy.index(r, 0)).row()
            entry = self.model.entry_at(src)
            if matcher(f"{entry.tag} {entry.message}"):
                rows.append(r)
        return rows

    def _update_match_label(self) -> None:
        if not self.search.text():
            self.match_label.setText("")
            return
        n = len(self._match_rows())
        self.match_label.setText(f"{n} match" if n == 1 else f"{n} matches")

    def _goto_match(self, step: int) -> None:
        rows = self._match_rows()
        if not rows:
            return
        cur = self.table.currentIndex().row()
        if step > 0:
            target = next((r for r in rows if r > cur), rows[0])
        else:
            target = next((r for r in reversed(rows) if r < cur), rows[-1])
        index = self.proxy.index(target, 0)
        self.table.setCurrentIndex(index)
        self.table.selectRow(target)
        self.table.scrollTo(index)
        self.match_label.setText(f"{rows.index(target) + 1}/{len(rows)}")

    # --- bookmarks ---------------------------------------------------------
    def _toggle_bookmark(self) -> None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        self.model.toggle_bookmark(self.proxy.mapToSource(idx).row())

    def _goto_bookmark(self, step: int) -> None:
        rows = []
        for src in self.model.bookmarked_rows():
            proxy_row = self.proxy.mapFromSource(self.model.index(src, 0)).row()
            if proxy_row >= 0:  # skip bookmarks hidden by the current filter
                rows.append(proxy_row)
        rows.sort()
        if not rows:
            return
        cur = self.table.currentIndex().row()
        if step > 0:
            target = next((r for r in rows if r > cur), rows[0])
        else:
            target = next((r for r in reversed(rows) if r < cur), rows[-1])
        index = self.proxy.index(target, 0)
        self.table.setCurrentIndex(index)
        self.table.selectRow(target)
        self.table.scrollTo(index)

    def _clear_bookmarks(self) -> None:
        self.model.clear_bookmarks()

    def eventFilter(self, obj, event) -> bool:
        # Ctrl + mouse wheel zooms the text (same as Ctrl+=/-), reusing _zoom so
        # it stays clamped and in sync across the log and detail panes. A plain
        # wheel is left alone so normal scrolling still works.
        if event.type() == QEvent.Wheel and event.modifiers() & Qt.ControlModifier:
            dy = event.angleDelta().y()
            if dy:
                self._zoom(1 if dy > 0 else -1)
            return True
        return super().eventFilter(obj, event)

    # --- font zoom ---------------------------------------------------------
    def _apply_font(self) -> None:
        size = max(6, min(28, BASE_FONT_PT + self._font_delta))
        for widget in (self.table, self.detail):
            font = widget.font()
            font.setPointSize(size)
            widget.setFont(font)
        fm = QFontMetrics(self.table.font())
        self.table.verticalHeader().setDefaultSectionSize(fm.height() + 4)

    def _zoom(self, step: int) -> None:
        self._font_delta = max(-4, min(12, self._font_delta + step))
        self._apply_font()

    def _reset_zoom(self) -> None:
        self._font_delta = 0
        self._apply_font()

    def _clear_device_buffer(self) -> None:
        """Wipe the device's on-device logcat ring buffer (adb logcat -c)."""
        serial = self._current_serial()
        if serial is None:
            self.statusBar().showMessage("Select a device first.")
            return
        ok = self._run_adb(
            lambda: clear_logcat(serial),
            missing_msg="adb not found.",
            error_prefix="Could not clear the device buffer",
            report=self.statusBar().showMessage,
        )
        if ok:
            # The on-device lines are gone; clear the stale view too so the button
            # visibly does something (a live stream then refills with fresh lines).
            self.model.clear()
            self.statusBar().showMessage(f"Cleared the device log buffer and view ({serial}).")

    # --- theme -------------------------------------------------------------
    def apply_theme(self, name: str) -> None:
        self._theme_name = name
        theme = THEMES[name]
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet(theme))
        self.model.set_level_colors(theme.level_colors)
        self.model.set_highlight_color(theme.search_highlight)
        self.model.set_bookmark_color(theme.bookmark)
        self.log_delegate.set_theme(
            theme.muted,
            theme.meta_text,
            theme.level_text,
            theme.base,
            theme.selection_bg,
            theme.selection_text,
            theme.row_hover_bg,
        )
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
        menu.addAction(self.bookmark_action)
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
        menu.addSeparator()
        mute = menu.addAction(f"Mute tag \u201c{tag}\u201d" if tag else "Mute tag")
        mute.setEnabled(bool(tag))
        mute.triggered.connect(lambda: self._mute_tag(tag))
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

    def _mute_tag(self, tag: str) -> None:
        """Hide a tag's lines by appending an exclude term to the query bar."""
        if not tag:
            return
        token = f"-{tag}"
        if token in self.query.text().split():
            return
        self.query.setText((self.query.text() + " " + token).strip())
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
            format_level_summary(
                self.model.rowCount(), self.model.level_counts(), self.proxy.rowCount()
            )
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

    def _settings_specs(self):
        """One (key, get, set) row per persisted setting — the single source of
        truth for save *and* restore, so the two can never drift apart. `get`
        returns the value to store; `set` applies a loaded value to the widgets.
        """

        def set_geometry(v):
            if v:
                self.restoreGeometry(QByteArray.fromBase64(v.encode("ascii")))

        def set_theme(v):
            name = v if v in THEMES else "Light"
            for act in self._theme_group.actions():
                act.setChecked(act.text() == name)
            self.apply_theme(name)

        def set_min_level(v):
            idx = self.level_box.findData(v)
            if idx >= 0:
                self.level_box.setCurrentIndex(idx)

        def set_show_details(v):
            self.details_action.setChecked(bool(v))
            self.detail.setVisible(self.details_action.isChecked())

        def set_hidden_columns(v):
            # Columns are superseded by the single-line log delegate; the key is
            # accepted for back-compat but ignored.
            return

        def set_tag_highlights(v):
            if isinstance(v, dict):
                for tag, color in v.items():
                    self.model.set_tag_color(str(tag), str(color))

        def set_tail_count(v):
            count = v if v in self._tail_actions else 0
            self._tail_actions[count].setChecked(True)

        def set_max_rows(v):
            cap = v if v in self._max_rows_actions else 0
            self._max_rows_actions[cap].setChecked(True)
            self.model.set_max_rows(cap)

        def set_log_buffers(v):
            names = v if isinstance(v, list) else []
            for name, act in self._buffer_actions.items():
                act.setChecked(name in names)

        def set_search_history(v):
            self._history = normalize_history(v)
            self._history_model.setStringList(self._history)

        def set_font_delta(v):
            delta = v if isinstance(v, int) else 0
            self._font_delta = max(-4, min(12, delta))
            self._apply_font()

        def set_time_mode(v):
            mode = v if v in self._time_actions else "absolute"
            self._time_actions[mode].setChecked(True)
            self.model.set_time_mode(mode)

        def set_search_mode(v):
            idx = self.search_mode_box.findData(v if v in ("filter", "highlight") else "filter")
            if idx >= 0:
                self.search_mode_box.setCurrentIndex(idx)

        def set_filter_presets(v):
            self._presets = normalize_presets(v)
            self._rebuild_presets_menu()

        def set_last_device(v):
            # Reselect the saved device in the already-populated picker
            # (refresh_devices ran in __init__, before settings loaded).
            self.devctl.preferred_serial = v or None
            if self.devctl.preferred_serial is not None:
                idx = self.device_box.findData(self.devctl.preferred_serial)
                if idx >= 0:
                    self.device_box.setCurrentIndex(idx)

        specs = [
            (
                "geometry",
                lambda: bytes(self.saveGeometry().toBase64()).decode("ascii"),
                set_geometry,
            ),
            ("theme", lambda: self._theme_name, set_theme),
            (
                "follow",
                self.follow_check.isChecked,
                lambda v: self.follow_check.setChecked(bool(v)),
            ),
            ("min_level", self.level_box.currentData, set_min_level),
            (
                "regex",
                self.regex_check.isChecked,
                lambda v: self.regex_check.setChecked(bool(v)),
            ),
            (
                "case",
                self.case_check.isChecked,
                lambda v: self.case_check.setChecked(bool(v)),
            ),
            ("tag_highlights", self.model.tag_colors, set_tag_highlights),
            ("show_details", self.details_action.isChecked, set_show_details),
            ("hidden_columns", lambda: [], set_hidden_columns),
            (
                "clear_on_start",
                self.clear_on_start_action.isChecked,
                lambda v: self.clear_on_start_action.setChecked(bool(v)),
            ),
            (
                "last_device",
                lambda: self.device_box.currentData() or self.devctl.preferred_serial or "",
                set_last_device,
            ),
            ("filter_presets", lambda: self._presets, set_filter_presets),
            ("search_mode", self.search_mode_box.currentData, set_search_mode),
            (
                "time_mode",
                lambda: next(
                    (m for m, a in self._time_actions.items() if a.isChecked()), "absolute"
                ),
                set_time_mode,
            ),
            ("font_delta", lambda: self._font_delta, set_font_delta),
            ("search_history", lambda: self._history, set_search_history),
            (
                "log_buffers",
                lambda: [n for n, a in self._buffer_actions.items() if a.isChecked()],
                set_log_buffers,
            ),
            (
                "tail_count",
                lambda: next((c for c, a in self._tail_actions.items() if a.isChecked()), 0),
                set_tail_count,
            ),
            (
                "max_rows",
                lambda: next((c for c, a in self._max_rows_actions.items() if a.isChecked()), 0),
                set_max_rows,
            ),
        ]
        # Guard against a setting being added to DEFAULTS but not here (or vice
        # versa) — the exact drift that silently breaks save/restore.
        assert {key for key, _, _ in specs} == set(DEFAULTS), (
            "settings specs out of sync with DEFAULTS"
        )
        return specs

    def _load_and_apply_settings(self) -> None:
        data = load_settings(str(self._settings_path()))
        for key, _get, set_value in self._settings_specs():
            set_value(data.get(key, DEFAULTS[key]))
        self.table.viewport().update()

    def _save_settings(self) -> None:
        data = {key: get_value() for key, get_value, _set in self._settings_specs()}
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
        buffers = [name for name, act in self._buffer_actions.items() if act.isChecked()]
        tail = next((c for c, a in self._tail_actions.items() if a.isChecked()), 0)
        self.reader = AdbReader(serial=serial, buffers=buffers or None, tail=tail)
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
        self.device_box.setEnabled(bool(self.devctl.devices))
        self.stop_btn.setEnabled(False)
        self._update_start_enabled()
        self.statusBar().showMessage("Stopped.")

    def on_batch(self, entries) -> None:
        # Follow is a stable manual toggle. Tail only when it is on AND the view is
        # already at the bottom, so scrolling up to read history is never yanked by
        # incoming logs; scrolling back to the bottom resumes tailing on its own.
        # Capture "at bottom" before appending, since appending grows the range.
        sb = self.table.verticalScrollBar()
        was_at_bottom = sb.value() >= sb.maximum() - 4
        self.model.append_entries(entries)
        if self.devctl.filtering:
            self._track_new_pids(entries)
        if self.follow_check.isChecked() and was_at_bottom:
            self.table.scrollToBottom()

    def _track_new_pids(self, entries) -> None:
        """Keep an active package filter live: add PIDs of newly started
        processes of the filtered package (so a restart keeps showing)."""
        if self.devctl.track(entries):
            self.proxy.set_pids(self.devctl.filter_pids)
            pids = ", ".join(sorted(self.devctl.filter_pids))
            self.statusBar().showMessage(
                f"{self.devctl.filter_package} restarted → tracking pid {pids}."
            )

    def on_error(self, msg: str) -> None:
        self.statusBar().showMessage(msg)
        self.stop()

    def closeEvent(self, event) -> None:
        self._save_settings()
        self.stop()
