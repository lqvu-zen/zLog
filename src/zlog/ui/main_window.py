"""The main window: wires the reader, model, filters and table together.

Data flow:

    AdbReader (thread) --batch_ready--> LogTableModel (master list)
                                              |
                                        LogFilterProxy (level + text + package PIDs)
                                              |
                                         QTableView (what you see)
"""

from __future__ import annotations

import os
import re
import shlex
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, QEvent, QStandardPaths, QStringListModel, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QFont,
    QFontMetrics,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QCompleter,
    QDialog,
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabBar,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zlog.adb.devices import list_devices
from zlog.adb.packages import clear_logcat, list_packages, resolve_pids
from zlog.adb.processes import list_process_map
from zlog.adb.reader import AdbReader
from zlog.core.autosave import AUTOSAVE_CAP, rotate_path, should_rotate
from zlog.core.bundle import make_bundle, parse_bundle
from zlog.core.devices import Device, is_serial_streamable
from zlog.core.diff import diff_logs, line_key
from zlog.core.export import to_csv, to_html, to_json, to_markdown, to_messages
from zlog.core.heat import heat_marks
from zlog.core.history import normalize_history, push_history
from zlog.core.models import LEVEL_RANK, LogEntry
from zlog.core.palette import match_commands
from zlog.core.plugins import load_colorizers
from zlog.core.presets import (
    make_preset,
    normalize_presets,
    preset_summary,
    remove_preset,
    upsert_preset,
)
from zlog.core.query import parse_query
from zlog.core.search import compile_matcher
from zlog.core.session import entries_to_text, text_to_entries
from zlog.core.settings import DEFAULTS, load_settings, save_settings
from zlog.core.sparkline import error_rate_sparkline
from zlog.core.summary import format_level_summary, tag_counts
from zlog.ui.device_controller import DeviceController
from zlog.ui.heat_scrollbar import HeatScrollBar
from zlog.ui.log_delegate import LogItemDelegate
from zlog.ui.log_model import COLUMNS
from zlog.ui.log_session import LogSession
from zlog.ui.query_line_edit import QueryLineEdit
from zlog.ui.settings_dialog import SettingsDialog
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
    _open_windows: list = []  # keeps New-Window spawns alive (not garbage-collected)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("zLog — Android Log Viewer")
        self.resize(1100, 700)

        # Runtime state, created before widgets so slots can rely on it existing.
        self.devctl = DeviceController(self)  # device picker + package/PID filter state
        self._theme_name = "Light"
        self._presets: list[dict] = []  # saved filter presets
        self._font_delta = 0  # point-size offset for the table + detail pane
        self._max_rows = 0  # ring-buffer cap (0 = unlimited), any value
        self._query_package = ""  # last package resolved from the query bar
        self._syncing_level = False  # guard: programmatic level_box sets skip the query mirror
        self._history: list[str] = []  # recent query-bar entries
        self._recent: list[str] = []  # recently opened/saved .log paths
        self._autosave_cap = AUTOSAVE_CAP  # bytes before the autosave file rolls over
        self._watch = None  # compiled substring matcher, or None
        self._watch_pattern = ""
        self._watch_last = 0.0  # monotonic time of last notification (throttle)
        self._tray = None  # lazily-created system-tray icon
        self._sessions: list[LogSession] = []  # capture tabs; re-rooted via properties
        self._active_index = 0
        self._heat_timer = QTimer(self)  # debounce heat-mark recompute
        self._heat_timer.setSingleShot(True)
        self._heat_timer.setInterval(400)
        self._heat_timer.timeout.connect(self._recompute_heat)
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
        self._maybe_reopen_last()
        self._load_plugins()

    # --- active-session re-rooting (tabs) ----------------------------------
    def _make_session(self) -> LogSession:
        sess = LogSession(self)
        self._wire_session_signals(sess)
        return sess

    def _wire_session_signals(self, sess) -> None:
        sess.model.rowsInserted.connect(self._update_counts)
        sess.model.modelReset.connect(self._update_counts)
        for sig in (
            sess.proxy.rowsInserted,
            sess.proxy.rowsRemoved,
            sess.proxy.modelReset,
            sess.proxy.layoutChanged,
        ):
            sig.connect(self._schedule_heat)
            sig.connect(self._update_placeholder)
            sig.connect(self._update_counts)
        sess.reconnect_timer.timeout.connect(lambda s=sess: self._try_reconnect(s))

    # --- tabs --------------------------------------------------------------
    def _rebind_selection(self) -> None:
        self.table.selectionModel().currentChanged.connect(self._update_detail)

    def _save_toolbar(self, sess) -> None:
        sess.query = self.query.text()
        sess.serial = self.device_box.currentData() or ""
        sess.level = self.level_box.currentData()
        sess.package = self.package_box.currentText()

    def _load_toolbar(self, sess) -> None:
        di = self.device_box.findData(sess.serial)
        if di >= 0:
            self.device_box.setCurrentIndex(di)
        self.package_box.setEditText(sess.package)
        # The session query carries the level: token, so it drives the dropdown +
        # proxy via _apply_query — no separate level_box set needed.
        self.query.setText(sess.query)

    def _set_tab_label(self, sess) -> None:
        if sess in self._sessions:
            i = self._sessions.index(sess)
            name = sess.serial or "Device"
            self.tab_bar.setTabText(i, f"\u25cf {name}" if sess.reader is not None else name)

    def _update_tab_closability(self) -> None:
        """Only show a close (x) on a tab when there's another one to fall back
        to — with one session left, _close_tab is a no-op, so a close button
        there just invites a click that silently does nothing."""
        if len(self._sessions) <= 1:
            self.tab_bar.setTabButton(0, QTabBar.RightSide, None)
        else:
            # Re-toggling regenerates the default close button on every tab,
            # including the one that was hidden while alone.
            self.tab_bar.setTabsClosable(False)
            self.tab_bar.setTabsClosable(True)

    def _new_tab(self) -> None:
        self._save_toolbar(self._active)
        self._sessions.append(self._make_session())
        idx = self.tab_bar.addTab("Device")
        self._update_tab_closability()
        self.tab_bar.setCurrentIndex(idx)  # -> _switch_tab

    def _switch_tab(self, index: int) -> None:
        if index < 0 or index >= len(self._sessions):
            return
        if index != self._active_index:
            self._save_toolbar(self._sessions[self._active_index])
        self._active_index = index
        self.table.setModel(self.proxy)
        self._rebind_selection()
        self._load_toolbar(self._active)
        self._update_counts()
        self._schedule_heat()
        self._update_placeholder()
        streaming = self._active.reader is not None
        self.stop_btn.setEnabled(streaming)
        self.pause_btn.setEnabled(streaming)
        self._update_start_enabled()

    def _close_tab(self, index: int) -> None:
        if len(self._sessions) <= 1:
            return  # always keep one tab
        sess = self._sessions[index]
        sess.want_stream = False
        sess.reconnect_timer.stop()
        if sess.reader:
            sess.reader.stop()
        self._sessions.pop(index)
        if self._active_index >= len(self._sessions):
            self._active_index = len(self._sessions) - 1
        self.tab_bar.removeTab(index)  # -> _switch_tab(current)
        self._update_tab_closability()

    @property
    def _active(self) -> LogSession:
        return self._sessions[self._active_index]

    @property
    def model(self):
        return self._active.model

    @property
    def proxy(self):
        return self._active.proxy

    @property
    def reader(self):
        return self._active.reader

    @reader.setter
    def reader(self, value):
        self._active.reader = value

    @property
    def _paused(self):
        return self._active.paused

    @_paused.setter
    def _paused(self, value):
        self._active.paused = value

    @property
    def _pause_buffer(self):
        return self._active.pause_buffer

    @_pause_buffer.setter
    def _pause_buffer(self, value):
        self._active.pause_buffer = value

    @property
    def _want_stream(self):
        return self._active.want_stream

    @_want_stream.setter
    def _want_stream(self, value):
        self._active.want_stream = value

    @property
    def _reconnect_serial(self):
        return self._active.reconnect_serial

    @_reconnect_serial.setter
    def _reconnect_serial(self, value):
        self._active.reconnect_serial = value

    @property
    def _last_time(self):
        return self._active.last_time

    @_last_time.setter
    def _last_time(self, value):
        self._active.last_time = value

    @property
    def _reconnect_timer(self):
        return self._active.reconnect_timer

    # --- construction (called once, in order, from __init__) ---------------
    def _build_widgets(self) -> None:
        """Create the model/proxy/view and every toolbar widget (no layout yet)."""
        self._sessions = [self._make_session()]
        self._active_index = 0
        self.tab_bar = QTabBar()
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.addTab("Device")
        self._update_tab_closability()

        self.table = LogTableView()
        self.table.setModel(self.proxy)
        self.heat_bar = HeatScrollBar()  # scrollbar with error-position ticks
        self.table.setVerticalScrollBar(self.heat_bar)
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
        self.log_delegate.view = self.table
        # Copy (Ctrl+C) and Select All: keyboard shortcuts via addAction, plus a
        # custom right-click menu that also offers per-tag highlighting.
        self.copy_action = QAction("Copy", self)
        self.copy_action.setShortcut(QKeySequence.Copy)
        # Only handle Ctrl+C when the table (or a child) has focus, so a selection
        # in the detail pane copies its own text instead of the whole log line.
        self.copy_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
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
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setToolTip("Pause the view (keep capturing; new lines buffer until Resume)")
        self.pause_btn.setEnabled(False)
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
        self.presets_list = QListWidget()
        self.presets_list.setToolTip("Double-click a saved filter to apply it")
        self.save_filter_btn = QPushButton("Save current filter…")
        self.update_filter_btn = QPushButton("Update to current")
        self.update_filter_btn.setToolTip(
            "Overwrite the selected saved filter with the current filter"
        )
        self.rename_filter_btn = QPushButton("Rename")
        self.delete_filter_btn = QPushButton("Delete")
        self.preset_preview = QLabel("")
        self.preset_preview.setWordWrap(True)
        self.spark_label = QLabel("")
        self.spark_label.setToolTip("Error rate over the last 500 lines")

        # Single query bar, parsed into the filters.
        self.query = QueryLineEdit()
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
        top_row.addWidget(self.pause_btn)
        top_row.addWidget(self.clear_btn)
        top_row.addSpacing(12)
        top_row.addWidget(self._vsep())
        top_row.addSpacing(12)
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

        # Filter bar: the query box on its own full-width row, plus match
        # navigation (F3/Shift+F3) feedback for the free-text portion of it.
        filter_row = QHBoxLayout()
        filter_row.addWidget(self.query)
        filter_row.addWidget(self.match_prev_btn)
        filter_row.addWidget(self.match_next_btn)
        filter_row.addWidget(self.match_label)

        layout = QVBoxLayout()
        layout.addWidget(self.tab_bar)
        layout.addLayout(top_row)
        layout.addLayout(filter_row)
        layout.addWidget(self._splitter)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(6, 6, 6, 6)
        panel_layout.addWidget(QLabel("Saved Filters"))
        panel_layout.addWidget(self.presets_list)
        panel_layout.addWidget(self.preset_preview)
        row1 = QHBoxLayout()
        row1.addWidget(self.save_filter_btn)
        row1.addWidget(self.update_filter_btn)
        panel_layout.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(self.rename_filter_btn)
        row2.addWidget(self.delete_filter_btn)
        panel_layout.addLayout(row2)
        self.presets_dock = QDockWidget("Saved Filters", self)
        self.presets_dock.setObjectName("presetsDock")
        self.presets_dock.setWidget(panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.presets_dock)
        self.setStatusBar(QStatusBar())
        self.statusBar().addPermanentWidget(self.spark_label)
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
        new_window_act = file_menu.addAction("New &Window")
        new_window_act.setShortcut("Ctrl+Shift+N")
        new_window_act.triggered.connect(self._new_window)
        new_tab_act = file_menu.addAction("New &Tab")
        new_tab_act.setShortcut("Ctrl+T")
        new_tab_act.triggered.connect(self._new_tab)
        file_menu.addSeparator()
        open_act = file_menu.addAction("&Open Log…")
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_log)
        self._recent_menu = file_menu.addMenu("Open &Recent")
        self._rebuild_recent_menu()
        save_act = file_menu.addAction("&Save Log…")
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_log)
        save_filtered_act = file_menu.addAction("Save &Filtered Log…")
        save_filtered_act.triggered.connect(self.save_filtered_log)

        file_menu.addSeparator()
        save_session_act = file_menu.addAction("Save Sess&ion…")
        save_session_act.triggered.connect(self.save_session)
        open_session_act = file_menu.addAction("Open Se&ssion…")
        open_session_act.triggered.connect(self.open_session)
        diff_act = file_menu.addAction("&Diff Against File…")
        diff_act.triggered.connect(self._diff_against_file)
        file_menu.addSeparator()
        export_menu = file_menu.addMenu("&Export")
        for name, fmt, ext in (
            ("CSV", to_csv, "csv"),
            ("JSON", to_json, "json"),
            ("HTML", to_html, "html"),
        ):
            act = export_menu.addAction(f"{name}…")
            act.triggered.connect(
                lambda _checked=False, n=name, f=fmt, e=ext: self._export(n, f, e)
            )

        view_menu = self.menuBar().addMenu("&View")

        # Preference actions are created here as standalone objects (the state the
        # Settings dialog reads/writes) but are NOT put in the View menu — the View
        # menu keeps only commands + navigation. See _build_menus / settings_dialog.
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        for name in THEMES:
            act = QAction(name, self)
            act.setCheckable(True)
            act.setChecked(name == "Light")
            self._theme_group.addAction(act)
            act.triggered.connect(lambda _checked=False, n=name: self.apply_theme(n))

        self.details_action = QAction("Show Details", self)
        self.details_action.setCheckable(True)
        self.details_action.setChecked(True)
        self.details_action.toggled.connect(self.detail.setVisible)
        self.clear_on_start_action = QAction("Clear on Start", self)
        self.clear_on_start_action.setCheckable(True)
        self.reopen_last_action = QAction("Reopen Last Log on Launch", self)
        self.reopen_last_action.setCheckable(True)
        self.autosave_action = QAction("Autosave Capture", self)
        self.autosave_action.setCheckable(True)
        self.autosave_action.toggled.connect(self._on_autosave_toggled)
        self.process_action = QAction("Show Process Names", self)
        self.process_action.setCheckable(True)
        self.process_action.toggled.connect(self._on_process_toggled)
        self.collapse_action = QAction("Collapse Repeated Lines", self)
        self.collapse_action.setCheckable(True)
        self.collapse_action.toggled.connect(self.proxy.set_collapse)
        self.case_action = QAction("Case sensitive", self)
        self.case_action.setCheckable(True)
        self.case_action.toggled.connect(self._on_case_toggled)
        self.highlight_action = QAction("Highlight matches", self)
        self.highlight_action.setCheckable(True)
        self.highlight_action.toggled.connect(self._on_highlight_toggled)

        self._time_group = QActionGroup(self)
        self._time_group.setExclusive(True)
        self._time_actions = {}
        for mode, label in (
            ("absolute", "Absolute"),
            ("since_start", "Since start"),
            ("delta", "Delta"),
        ):
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(mode == "absolute")
            self._time_group.addAction(act)
            act.triggered.connect(lambda _c=False, m=mode: self.model.set_time_mode(m))
            self._time_actions[mode] = act

        self._buffer_actions = {}
        for name in ("main", "system", "crash", "radio", "events", "kernel"):
            act = QAction(name, self)
            act.setCheckable(True)
            self._buffer_actions[name] = act

        self._tail_group = QActionGroup(self)
        self._tail_group.setExclusive(True)
        self._tail_actions = {}
        for count, label in (
            (0, "Whole buffer"),
            (500, "Last 500"),
            (1000, "Last 1000"),
            (5000, "Last 5000"),
        ):
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(count == 0)
            self._tail_group.addAction(act)
            self._tail_actions[count] = act

        # --- command / navigation items (these stay in the View menu) ---
        clear_filters_act = view_menu.addAction("Clear F&ilters")
        clear_filters_act.triggered.connect(self.clear_filters)
        next_problem_act = view_menu.addAction("Next Problem")
        next_problem_act.setShortcut("F2")
        next_problem_act.triggered.connect(lambda: self._goto_severity(1))
        prev_problem_act = view_menu.addAction("Previous Problem")
        prev_problem_act.setShortcut("Shift+F2")
        prev_problem_act.triggered.connect(lambda: self._goto_severity(-1))
        tag_summary_act = view_menu.addAction("&Tag Summary…")
        tag_summary_act.triggered.connect(self._show_tag_summary)
        watch_act = view_menu.addAction("Set &Watch…")
        watch_act.triggered.connect(self._set_watch_dialog)
        reload_plugins_act = view_menu.addAction("Reload &Plugins")
        reload_plugins_act.triggered.connect(self._load_plugins)
        view_menu.addAction(self.presets_dock.toggleViewAction())
        self.presets_menu = view_menu.addMenu("Filter &Presets")
        self._rebuild_presets_menu()

        view_menu.addSeparator()
        next_bm = view_menu.addAction("Next Bookmark")
        next_bm.setShortcut("Ctrl+F2")
        next_bm.triggered.connect(lambda: self._goto_bookmark(1))
        prev_bm = view_menu.addAction("Previous Bookmark")
        prev_bm.setShortcut("Ctrl+Shift+F2")
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

        clear_buf_act = view_menu.addAction("Clear device log &buffer")
        clear_buf_act.triggered.connect(self._clear_device_buffer)

        self._settings_act = self.menuBar().addAction("&Settings…")
        self._settings_act.triggered.connect(self._open_settings)

    def _connect_signals(self) -> None:
        """Wire toolbar/model/proxy signals to their slots (menu actions wire
        themselves in _build_menus)."""
        self.refresh_btn.clicked.connect(self.refresh_devices)
        self.tab_bar.currentChanged.connect(self._switch_tab)
        self.tab_bar.tabCloseRequested.connect(self._close_tab)
        self.presets_list.itemActivated.connect(self._on_preset_activated)
        self.save_filter_btn.clicked.connect(self.save_current_preset)
        self.update_filter_btn.clicked.connect(self._update_preset_to_current)
        self.rename_filter_btn.clicked.connect(self._rename_preset)
        self.delete_filter_btn.clicked.connect(self._delete_selected_preset)
        self.presets_list.currentRowChanged.connect(self._update_preset_preview)
        self.to_top_btn.clicked.connect(self.table.scrollToTop)
        self.to_latest_btn.clicked.connect(self.table.scrollToBottom)
        self.device_box.currentIndexChanged.connect(self._update_start_enabled)
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.clear_btn.clicked.connect(self.model.clear)
        self.clear_device_btn.clicked.connect(self._clear_device_buffer)
        self.pause_btn.clicked.connect(self._toggle_pause)
        # Ctrl+wheel over the log or detail zooms (handled in eventFilter);
        # filter the viewports, since that is where wheel events are delivered.
        self.table.viewport().installEventFilter(self)
        self.detail.viewport().installEventFilter(self)
        self.load_pkgs_btn.clicked.connect(self.load_packages)
        self.apply_pkg_btn.clicked.connect(self.apply_package_filter)
        self.clear_pkg_btn.clicked.connect(self.clear_package_filter)
        self.package_box.lineEdit().returnPressed.connect(self.apply_package_filter)
        self.level_box.currentIndexChanged.connect(self._on_level_box_changed)
        self.search.textChanged.connect(self._apply_search)
        self.query.textChanged.connect(self._apply_query)
        self.query.returnPressed.connect(self._commit_query_history)
        self.exclude.textChanged.connect(self._apply_search)
        self.match_next_btn.clicked.connect(lambda: self._goto_match(1))
        self.match_prev_btn.clicked.connect(lambda: self._goto_match(-1))
        QShortcut(QKeySequence("F3"), self, activated=lambda: self._goto_match(1))
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self._open_command_palette)
        QShortcut(QKeySequence("Shift+F3"), self, activated=lambda: self._goto_match(-1))
        self.regex_check.toggled.connect(self._apply_search)
        self.case_check.toggled.connect(self._apply_search)
        self.search_mode_box.currentIndexChanged.connect(self._apply_search)
        self.clear_filters_btn.clicked.connect(self.clear_filters)
        self._rebind_selection()

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
        # The query bar owns every filter incl. the level floor, so clearing it
        # (via _apply_query) resets level/tag/search/exclude/package together.
        self.query.clear()
        self.statusBar().showMessage("Filters cleared.")

    def _on_level_box_changed(self) -> None:
        # A real user change of the Level dropdown mirrors into the query's level:
        # token so the two never disagree. Programmatic sets (from _apply_query
        # reflecting the query) are guarded out to avoid a signal loop.
        if self._syncing_level:
            return
        self._set_query_level(self.level_box.currentData() or "V")

    def _set_query_level(self, letter: str) -> None:
        """Write level:<letter> into the query (drop it for V), replacing any
        existing level: token. Drives _apply_query, which re-applies the filter."""
        try:
            tokens = shlex.split(self.query.text())
        except ValueError:
            tokens = self.query.text().split()
        kept = [t for t in tokens if not t.lower().startswith("level:")]
        if letter and letter != "V":
            kept.insert(0, f"level:{letter}")
        new_text = " ".join(shlex.quote(t) if any(ch.isspace() for ch in t) else t for t in kept)
        if new_text != self.query.text():
            self.query.setText(new_text)  # -> _apply_query

    def _set_level_box(self, letter: str) -> None:
        """Reflect a level into the dropdown without triggering the query mirror."""
        idx = self.level_box.findData(letter)
        if idx >= 0 and idx != self.level_box.currentIndex():
            self._syncing_level = True
            self.level_box.setCurrentIndex(idx)
            self._syncing_level = False

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
        self._rebuild_presets_list()

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
            query=self.query.text(),
        )
        self._presets = upsert_preset(self._presets, preset)
        self._rebuild_presets_menu()
        self._save_settings()
        self.statusBar().showMessage(f"Saved preset {name!r}.")

    def _apply_preset(self, preset: dict) -> None:
        self.case_check.setChecked(bool(preset.get("case")))
        level = preset.get("min_level", "V")
        if "query" in preset:
            # Newer presets store the raw query bar text verbatim, so tag:/-exclude/
            # regex/package tokens all survive.
            text = preset.get("query", "")
        else:
            # Legacy preset: reconstruct the query from the decomposed fields.
            parts = []
            package = preset.get("package", "")
            if package:
                parts.append(f"package:{package}")
            search = preset.get("search", "")
            if search:
                parts.append(f"/{search}/" if preset.get("regex") else search)
            text = " ".join(parts)
        # Fold the level floor into the query so it applies and the dropdown stays
        # in sync (unless a level: token is already present).
        if level and level != "V" and "level:" not in text.lower():
            text = f"level:{level} {text}".strip()
        self.query.setText(text)  # -> _apply_query drives the dropdown + proxy
        self.statusBar().showMessage(f"Applied preset {preset.get('name', '')!r}.")

    def _delete_preset(self, name: str) -> None:
        self._presets = remove_preset(self._presets, name)
        self._rebuild_presets_menu()
        self._save_settings()
        self.statusBar().showMessage(f"Deleted preset {name!r}.")

    def _rebuild_presets_list(self) -> None:
        self.presets_list.clear()
        for preset in self._presets:
            item = QListWidgetItem(preset["name"])
            item.setData(Qt.UserRole, preset["name"])
            item.setToolTip(preset_summary(preset))
            self.presets_list.addItem(item)
        self._update_preset_preview()

    def _on_preset_activated(self, item) -> None:
        name = item.data(Qt.UserRole)
        for preset in self._presets:
            if preset["name"] == name:
                self._apply_preset(preset)
                return

    def _delete_selected_preset(self) -> None:
        item = self.presets_list.currentItem()
        if item is not None:
            self._delete_preset(item.data(Qt.UserRole))

    def _selected_preset(self) -> dict | None:
        item = self.presets_list.currentItem()
        if item is None:
            return None
        name = item.data(Qt.UserRole)
        return next((p for p in self._presets if p["name"] == name), None)

    def _update_preset_preview(self, *args) -> None:
        preset = self._selected_preset()
        self.preset_preview.setText(preset_summary(preset) if preset else "")

    def _update_preset_to_current(self) -> None:
        preset = self._selected_preset()
        if preset is None:
            self.statusBar().showMessage("Select a saved filter to update.")
            return
        updated = make_preset(
            preset["name"],
            min_level=self.level_box.currentData(),
            search=self.search.text(),
            regex=self.regex_check.isChecked(),
            case=self.case_check.isChecked(),
            package=self.package_box.currentText().strip(),
            query=self.query.text(),
        )
        self._presets = upsert_preset(self._presets, updated)
        self._rebuild_presets_menu()
        self._save_settings()
        self.statusBar().showMessage(f"Updated {preset['name']!r} to the current filter.")

    def _rename_preset(self) -> None:
        preset = self._selected_preset()
        if preset is None:
            return
        name, ok = QInputDialog.getText(self, "Rename Filter", "New name:", text=preset["name"])
        name = name.strip()
        if not ok or not name or name == preset["name"]:
            return
        renamed = make_preset(
            name,
            min_level=preset["min_level"],
            search=preset["search"],
            regex=preset["regex"],
            case=preset["case"],
            package=preset["package"],
            query=preset.get("query", ""),
        )
        self._presets = upsert_preset(remove_preset(self._presets, preset["name"]), renamed)
        self._rebuild_presets_menu()
        self._save_settings()
        self.statusBar().showMessage(f"Renamed to {name!r}.")

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
            level = spec.level or "V"  # query is the source of truth; no token = V
            self._set_level_box(level)  # mirror into the dropdown (guarded)
            self.proxy.set_min_level(level)
        self.proxy.set_tag(spec.tag)
        self.proxy.set_query_pids(set(spec.pids) if spec.pids else None)
        self.proxy.set_proc(spec.process)
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

    # --- severity navigation ----------------------------------------------
    def _proxy_rank(self, proxy_row: int) -> int:
        src = self.proxy.mapToSource(self.proxy.index(proxy_row, 0)).row()
        return self.model.entry_at(src).rank

    def _schedule_heat(self, *args) -> None:
        self._heat_timer.start()

    def _recompute_heat(self) -> None:
        n = self.proxy.rowCount()
        marks = heat_marks((self._proxy_rank(r) for r in range(n)), n, LEVEL_RANK["E"])
        self.heat_bar.set_marks(marks, THEMES[self._theme_name].level_text["E"])

    def _goto_severity(self, step: int) -> None:
        """Jump to the next/previous visible warning-or-above line, wrapping."""
        n = self.proxy.rowCount()
        if n == 0:
            return
        threshold = LEVEL_RANK["W"]
        cur = self.table.currentIndex().row()
        forward = range(cur + 1, n) if step > 0 else range(cur - 1, -1, -1)
        wrap = range(n) if step > 0 else range(n - 1, -1, -1)
        for r in list(forward) + list(wrap):
            if self._proxy_rank(r) >= threshold:
                index = self.proxy.index(r, 0)
                self.table.setCurrentIndex(index)
                self.table.selectRow(r)
                self.table.scrollTo(index)
                return

    def _all_commands(self) -> list[tuple[str, QAction]]:
        """Every leaf menu action (into submenus), as (clean label, action)."""
        out: list[tuple[str, QAction]] = []

        def walk(menu):
            for act in menu.actions():
                sub = act.menu()
                if sub is not None:
                    walk(sub)
                elif act.text() and not act.isSeparator():
                    label = act.text().replace("&", "").replace("\u2026", "").strip()
                    out.append((label, act))

        for act in self.menuBar().actions():
            if act.menu() is not None:
                walk(act.menu())
        # Preference toggles live in the Settings dialog (not a menu) but stay
        # reachable from the command palette.
        extra = [
            self._settings_act,
            self.details_action,
            self.clear_on_start_action,
            self.reopen_last_action,
            self.autosave_action,
            self.process_action,
            self.collapse_action,
            self.case_action,
            self.highlight_action,
            *self._theme_group.actions(),
            *self._time_actions.values(),
            *self._buffer_actions.values(),
            *self._tail_actions.values(),
        ]
        for act in extra:
            if act.text():
                label = act.text().replace("&", "").replace("\u2026", "").strip()
                out.append((label, act))
        return out

    def _open_command_palette(self) -> None:
        """Ctrl+K: type to fuzzy-find and run any menu command."""
        cmds = self._all_commands()
        labels = [c[0] for c in cmds]
        dlg = QDialog(self)
        dlg.setWindowTitle("Command Palette")
        dlg.resize(420, 380)
        box = QLineEdit(dlg)
        box.setPlaceholderText("Type a command…")
        lst = QListWidget(dlg)

        def refresh():
            lst.clear()
            for idx in match_commands(labels, box.text()):
                item = QListWidgetItem(labels[idx])
                item.setData(Qt.UserRole, idx)
                lst.addItem(item)
            if lst.count():
                lst.setCurrentRow(0)

        def run(item=None):
            item = item or lst.currentItem()
            if item is None:
                return
            idx = item.data(Qt.UserRole)
            dlg.accept()
            cmds[idx][1].trigger()

        box.textChanged.connect(refresh)
        box.returnPressed.connect(lambda: run())
        lst.itemActivated.connect(run)
        layout = QVBoxLayout(dlg)
        layout.addWidget(box)
        layout.addWidget(lst)
        refresh()
        box.setFocus()
        dlg.exec()

    def _diff_against_file(self) -> None:
        """Compare the current log with another saved log (unified, colored diff)."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Diff Against File", "", "Log files (*.log);;All files (*)"
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                other = fh.read()
        except OSError as exc:
            self.statusBar().showMessage(f"Could not open: {exc}")
            return
        a = [line_key(e) for e in self.model.all_entries()]
        b = [line_key(e) for e in text_to_entries(other)]
        rows = diff_logs(a, b)
        added = sum(1 for op, _ in rows if op == "+")
        removed = sum(1 for op, _ in rows if op == "-")
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Diff — {removed} removed, {added} added vs {Path(path).name}")
        dlg.resize(760, 560)
        lst = QListWidget(dlg)
        mono = QFont()
        mono.setFamilies(LOG_FONT_FAMILIES)
        mono.setStyleHint(QFont.Monospace)
        lst.setFont(mono)
        colors = {"-": QColor("#c62828"), "+": QColor("#2e7d32"), " ": QColor("#9aa0a6")}
        for op, line in rows:
            item = QListWidgetItem(f"{op} {line}")
            item.setForeground(colors[op])
            lst.addItem(item)
        layout = QVBoxLayout(dlg)
        layout.addWidget(lst)
        dlg.exec()

    # --- plugins -----------------------------------------------------------
    def _plugins_dir(self) -> str:
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        return str(Path(base) / "plugins")

    def _load_plugins(self) -> None:
        path = self._plugins_dir()
        os.makedirs(path, exist_ok=True)
        colorizers, errors = load_colorizers(path)
        self.model.set_colorizers(colorizers)
        self.table.viewport().update()
        msg = f"Loaded {len(colorizers)} colorizer plugin(s) from {path}."
        if errors:
            msg += f" {len(errors)} failed."
        self.statusBar().showMessage(msg)

    # --- watch pattern -----------------------------------------------------
    def _set_watch_dialog(self) -> None:
        text, ok = QInputDialog.getText(
            self,
            "Watch Pattern",
            "Notify on lines containing (blank to clear):",
            text=self._watch_pattern,
        )
        if ok:
            self._apply_watch(text)

    def _apply_watch(self, pattern: str, announce: bool = True) -> None:
        self._watch_pattern = pattern or ""
        self._watch = (
            compile_matcher(self._watch_pattern, regex=False) if self._watch_pattern else None
        )
        if announce:
            msg = f'Watching for "{pattern}".' if pattern else "Watch cleared."
            self.statusBar().showMessage(msg)

    def _watch_hits(self, entries) -> list:
        if self._watch is None:
            return []
        return [e for e in entries if self._watch(f"{e.tag} {e.message}")]

    def _ensure_tray(self):
        from PySide6.QtWidgets import QSystemTrayIcon

        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        if self._tray is None:
            self._tray = QSystemTrayIcon(self.windowIcon(), self)
            self._tray.show()
        return self._tray

    def _notify_watch(self, entry) -> None:
        now = time.monotonic()
        if now - self._watch_last < 3.0:  # throttle bursts
            return
        self._watch_last = now
        text = f"{entry.tag}: {entry.message}"[:120]
        tray = self._ensure_tray()
        if tray is not None:
            tray.showMessage("zLog watch match", text)
        else:
            self.statusBar().showMessage(f"Watch match — {text}")
            QApplication.beep()

    def _show_tag_summary(self) -> None:
        """Modal list of tags in the current view by count; double-click filters."""
        rows = tag_counts(self._filtered_entries())
        dlg = QDialog(self)
        dlg.setWindowTitle("Tag Summary")
        dlg.resize(360, 440)
        table = QTableWidget(len(rows), 2, dlg)
        table.setHorizontalHeaderLabels(["Tag", "Count"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i, (tag, count) in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(tag))
            cell = QTableWidgetItem(str(count))
            cell.setTextAlignment(int(Qt.AlignRight | Qt.AlignVCenter))
            table.setItem(i, 1, cell)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

        def use(row: int, _col: int) -> None:
            self.query.setText(f"tag:{rows[row][0]}")  # -> _apply_query
            dlg.accept()

        table.cellDoubleClicked.connect(use)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("Double-click a tag to filter to it:"))
        layout.addWidget(table)
        dlg.exec()

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
        self._apply_row_height()

    def _apply_row_height(self) -> None:
        """Wrap on: size each row to its full (wrapped) message. Off: uniform one line."""
        vh = self.table.verticalHeader()
        fm = QFontMetrics(self.table.font())
        vh.setDefaultSectionSize(fm.height() + 4)
        if self.log_delegate.wrap:
            vh.setSectionResizeMode(QHeaderView.ResizeToContents)
        else:
            # Back to a uniform single line: switching off ResizeToContents keeps the
            # previously-grown section sizes, so re-fit rows to the (now one-line) hint.
            vh.setSectionResizeMode(QHeaderView.Fixed)
            self.table.resizeRowsToContents()

    def _zoom(self, step: int) -> None:
        self._font_delta = max(-4, min(12, self._font_delta + step))
        self._apply_font()

    def _reset_zoom(self) -> None:
        self._font_delta = 0
        self._apply_font()

    def _set_font_delta(self, n: int) -> None:
        self._font_delta = max(-4, min(12, int(n)))
        self._apply_font()

    # --- settings dialog ---------------------------------------------------
    def _collect_settings(self) -> dict:
        """Snapshot the current preference state for the Settings dialog."""
        time_mode = next((m for m, a in self._time_actions.items() if a.isChecked()), "absolute")
        tail = next((c for c, a in self._tail_actions.items() if a.isChecked()), 0)
        return {
            "theme": self._theme_name,
            "font_delta": self._font_delta,
            "show_details": self.details_action.isChecked(),
            "time_mode": time_mode,
            "highlight": self.highlight_action.isChecked(),
            "case": self.case_action.isChecked(),
            "collapse": self.collapse_action.isChecked(),
            "show_process": self.process_action.isChecked(),
            "buffers": {n for n, a in self._buffer_actions.items() if a.isChecked()},
            "tail": tail,
            "max_rows": self._max_rows,
            "clear_on_start": self.clear_on_start_action.isChecked(),
            "follow": self.follow_check.isChecked(),
            "reopen_last": self.reopen_last_action.isChecked(),
            "autosave": self.autosave_action.isChecked(),
            "wrap": self.log_delegate.wrap,
        }

    def _open_settings(self) -> None:
        dlg = SettingsDialog(
            self._collect_settings(),
            themes=list(THEMES),
            time_modes=[
                ("Absolute", "absolute"),
                ("Since start", "since_start"),
                ("Delta", "delta"),
            ],
            tail_options=[
                ("Whole buffer", 0),
                ("Last 500", 500),
                ("Last 1000", 1000),
                ("Last 5000", 5000),
            ],
            buffers=["main", "system", "crash", "radio", "events", "kernel"],
            parent=self,
        )
        if dlg.exec():
            self._apply_settings_values(dlg.get_values())
            self.statusBar().showMessage("Settings applied.")

    def _apply_settings_values(self, v: dict) -> None:
        """Drive the existing backing actions/widgets from the dialog's values."""
        self.apply_theme(v["theme"])
        for act in self._theme_group.actions():
            act.setChecked(act.text() == v["theme"])
        self._set_font_delta(v["font_delta"])
        self.details_action.setChecked(v["show_details"])
        mode = v["time_mode"]
        if mode in self._time_actions:
            self._time_actions[mode].setChecked(True)
            self.model.set_time_mode(mode)
        self.highlight_action.setChecked(v["highlight"])
        self.case_action.setChecked(v["case"])
        self.collapse_action.setChecked(v["collapse"])
        self.process_action.setChecked(v["show_process"])
        for name, act in self._buffer_actions.items():
            act.setChecked(name in v["buffers"])
        if v["tail"] in self._tail_actions:
            self._tail_actions[v["tail"]].setChecked(True)
        self._max_rows = max(0, int(v["max_rows"]))
        self.model.set_max_rows(self._max_rows)
        self.clear_on_start_action.setChecked(v["clear_on_start"])
        self.follow_check.setChecked(v["follow"])
        self.reopen_last_action.setChecked(v["reopen_last"])
        self.autosave_action.setChecked(v["autosave"])
        self.log_delegate.wrap = bool(v["wrap"])
        self._apply_row_height()
        self.table.viewport().update()
        self._save_settings()

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
        self._schedule_heat()  # recolor error ticks for the new theme

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

    def _copy_markdown(self) -> None:
        entries = self._selected_entries()
        if not entries:
            return
        QApplication.clipboard().setText(to_markdown(entries))
        self.statusBar().showMessage(f"Copied {len(entries)} line(s) as Markdown.")

    def _copy_messages(self) -> None:
        entries = self._selected_entries()
        if not entries:
            return
        QApplication.clipboard().setText(to_messages(entries))
        self.statusBar().showMessage(f"Copied {len(entries)} message(s).")

    def _add_query_token(self, token: str) -> None:
        """Add `token` (key:value) to the query bar, replacing any token with the
        same key; values with spaces are quoted so parse_query reads them back."""
        key = token.split(":", 1)[0]
        try:
            tokens = shlex.split(self.query.text())
        except ValueError:
            tokens = self.query.text().split()
        kept = [t for t in tokens if not t.startswith(key + ":")]
        kept.append(token)
        self.query.setText(
            " ".join(shlex.quote(t) if any(ch.isspace() for ch in t) else t for t in kept)
        )
        self.statusBar().showMessage(f"Filter \u2192 {token}")

    def _show_table_menu(self, pos) -> None:
        menu = QMenu(self.table)
        menu.addAction(self.copy_action)
        copy_md = menu.addAction("Copy as Markdown")
        copy_md.triggered.connect(self._copy_markdown)
        copy_msg = menu.addAction("Copy message only")
        copy_msg.triggered.connect(self._copy_messages)
        menu.addAction(self.select_all_action)
        menu.addAction(self.bookmark_action)
        menu.addSeparator()
        index = self.table.indexAt(pos)
        entry = None
        if index.isValid():
            entry = self.model.entry_at(self.proxy.mapToSource(index).row())
        tag = entry.tag if entry else ""
        if entry is not None:
            filt = menu.addMenu("Filter to…")
            if entry.level:
                act = filt.addAction(f"Level \u2265 {entry.level}")
                act.triggered.connect(
                    lambda _c=False, lv=entry.level: self._add_query_token(f"level:{lv}")
                )
            if entry.tag:
                act = filt.addAction(f"Tag: {entry.tag}")
                act.triggered.connect(
                    lambda _c=False, tg=entry.tag: self._add_query_token(f"tag:{tg}")
                )
            if entry.pid:
                act = filt.addAction(f"PID: {entry.pid}")
                act.triggered.connect(
                    lambda _c=False, pid=entry.pid: self._add_query_token(f"pid:{pid}")
                )
            proc = self.model.process_name(entry.pid) if entry.pid else ""
            if proc:
                act = filt.addAction(f"Package: {proc}")
                act.triggered.connect(lambda _c=False, pr=proc: self._add_query_token(f"proc:{pr}"))
            filt.setEnabled(bool(entry.level or entry.tag or entry.pid))
            excl = menu.addMenu("Exclude…")
            ex_tag = excl.addAction(f"Tag: {entry.tag}" if entry.tag else "Tag")
            ex_tag.setEnabled(bool(entry.tag))
            ex_tag.triggered.connect(lambda _c=False, tg=entry.tag: self._mute_tag(tg))
            menu.addSeparator()
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
        self._remember_recent(path)

    def save_log(self) -> None:
        stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
        self._write_log(self.model.all_entries(), f"zlog-{stamp}.log")

    def save_filtered_log(self) -> None:
        stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
        self._write_log(self._filtered_entries(), f"zlog-{stamp}-filtered.log")

    def _export(self, name, formatter, ext) -> None:
        """Save the currently-visible entries via `formatter` (CSV/JSON/HTML)."""
        stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
        path, _ = QFileDialog.getSaveFileName(
            self, f"Export {name}", f"zlog-{stamp}.{ext}", f"{name} (*.{ext});;All files (*)"
        )
        if not path:
            return
        entries = self._filtered_entries()
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(formatter(entries))
        except OSError as exc:
            self.statusBar().showMessage(f"Could not export: {exc}")
            return
        self.statusBar().showMessage(f"Exported {len(entries)} lines to {Path(path).name}.")

    # --- sessions ----------------------------------------------------------
    def save_session(self) -> None:
        stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Session",
            f"zlog-{stamp}.zsession",
            "Session files (*.zsession);;All files (*)",
        )
        if path:
            self._write_session(path)

    def _write_session(self, path: str) -> None:
        text = make_bundle(
            entries_to_text(self.model.all_entries()),
            self.query.text(),
            self.model.tag_colors(),
            self.model.bookmarked_rows(),
        )
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            self.statusBar().showMessage(f"Could not save session: {exc}")
            return
        self.statusBar().showMessage(f"Saved session to {Path(path).name}.")

    def open_session(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Session", "", "Session files (*.zsession);;All files (*)"
        )
        if path:
            self._read_session(path)

    def _read_session(self, path: str) -> None:
        try:
            with open(path, encoding="utf-8") as fh:
                data = parse_bundle(fh.read())
        except OSError as exc:
            self.statusBar().showMessage(f"Could not open session: {exc}")
            return
        except ValueError:
            self.statusBar().showMessage("Not a valid session file.")
            return
        # Like Open: go offline and drop the device-specific PID filter.
        if self.reader and self.reader.isRunning():
            self.stop()
        self.proxy.set_pids(None)
        entries = text_to_entries(data["log"])
        self.model.clear()
        self.model.clear_process_names()  # offline: PIDs are from another capture
        self.model.append_entries(entries)
        self.model.clear_tag_colors()
        for tag, color in data["tag_highlights"].items():
            self.model.set_tag_color(tag, color)
        self.model.set_bookmarks(data["bookmarks"])
        self.query.setText(data["query"])  # -> _apply_query
        self.table.viewport().update()
        self.statusBar().showMessage(f"Loaded session from {Path(path).name}.")

    def _maybe_reopen_last(self) -> None:
        """On launch, reopen the most-recent log if the user opted in (and no live
        stream is running)."""
        if self.reopen_last_action.isChecked() and self._recent and self.reader is None:
            self._load_log_file(self._recent[0])

    # --- autosave ----------------------------------------------------------
    def _autosave_path(self) -> str:
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        return str(Path(base) / "autosave.log")

    def _on_autosave_toggled(self, checked: bool) -> None:
        if checked:
            self.statusBar().showMessage(f"Autosave on \u2192 {self._autosave_path()}")

    def _autosave(self, entries) -> None:
        if not (entries and self.autosave_action.isChecked()):
            return
        path = self._autosave_path()
        text = entries_to_text(entries)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            size = os.path.getsize(path) if os.path.exists(path) else 0
            if size and should_rotate(size, len(text.encode("utf-8")), self._autosave_cap):
                os.replace(path, rotate_path(path))  # keep one .1 backup
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            self.autosave_action.setChecked(False)  # stop retrying every batch
            self.statusBar().showMessage(f"Autosave off (write failed): {exc}")

    def _new_window(self) -> None:
        """Open a second, fully independent zLog window (stream another device)."""
        win = MainWindow()
        MainWindow._open_windows.append(win)
        win.show()

    def open_log(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Log", "", "Log files (*.log);;All files (*)"
        )
        if path:
            self._load_log_file(path)

    def _load_log_file(self, path: str) -> None:
        """Load a saved log into the offline view; used by Open and Open Recent."""
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            self.statusBar().showMessage(f"Could not open: {exc}")
            self._forget_recent(path)  # gone/moved -> drop it from the list
            return
        # Opening is an offline view: stop any live stream and drop the
        # device-specific package (PID) filter, which no longer applies.
        if self.reader and self.reader.isRunning():
            self.stop()
        self.proxy.set_pids(None)
        entries = text_to_entries(text)
        self.model.clear()
        self.model.clear_process_names()  # offline: PIDs are from another capture
        self.model.append_entries(entries)
        self.statusBar().showMessage(f"Loaded {len(entries)} lines from {Path(path).name}.")
        self._remember_recent(path)

    # --- recent files ------------------------------------------------------
    def _remember_recent(self, path: str) -> None:
        self._recent = push_history(self._recent, path, limit=10)
        self._rebuild_recent_menu()
        self._save_settings()

    def _forget_recent(self, path: str) -> None:
        if path in self._recent:
            self._recent = [p for p in self._recent if p != path]
            self._rebuild_recent_menu()
            self._save_settings()

    def _clear_recent(self) -> None:
        self._recent = []
        self._rebuild_recent_menu()
        self._save_settings()

    def _rebuild_recent_menu(self) -> None:
        self._recent_menu.clear()
        if not self._recent:
            act = self._recent_menu.addAction("(none)")
            act.setEnabled(False)
            return
        for path in self._recent:
            act = self._recent_menu.addAction(Path(path).name)
            act.setToolTip(path)
            act.triggered.connect(lambda _checked=False, p=path: self._load_log_file(p))
        self._recent_menu.addSeparator()
        self._recent_menu.addAction("Clear Recent").triggered.connect(self._clear_recent)

    # --- status counts -----------------------------------------------------
    def _update_counts(self, *args) -> None:
        total = self.model.rowCount()
        visible = self.proxy.rowCount()
        # Once a filter is hiding rows, tally the levels of what's actually shown
        # instead of the whole buffer — otherwise "Showing X of Y" reads as if the
        # per-level counts describe X when they'd still describe Y.
        counts = self.proxy.level_counts() if visible < total else self.model.level_counts()
        self.count_label.setText(format_level_summary(total, counts, visible))
        start = max(0, total - 500)
        ranks = [self.model.entry_at(r).rank for r in range(start, total)]
        self.spark_label.setText(error_rate_sparkline(ranks, LEVEL_RANK["E"]))

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

        def set_splitter_state(v):
            if v:
                self._splitter.restoreState(QByteArray.fromBase64(v.encode("ascii")))

        def set_theme(v):
            name = v if v in THEMES else "Light"
            for act in self._theme_group.actions():
                act.setChecked(act.text() == name)
            self.apply_theme(name)

        def set_min_level(v):
            self._set_query_level(v)

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
            self._max_rows = max(0, int(v))
            self.model.set_max_rows(self._max_rows)

        def set_log_buffers(v):
            names = v if isinstance(v, list) else []
            for name, act in self._buffer_actions.items():
                act.setChecked(name in names)

        def set_search_history(v):
            self._history = normalize_history(v)
            self._history_model.setStringList(self._history)

        def set_recent(v):
            self._recent = normalize_history(v, limit=10)
            self._rebuild_recent_menu()

        def set_watch(v):
            self._apply_watch(v if isinstance(v, str) else "", announce=False)

        def set_collapse(v):
            self.collapse_action.setChecked(bool(v))
            self.proxy.set_collapse(bool(v))

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

        def set_wrap(v):
            self.log_delegate.wrap = bool(v)
            self._apply_row_height()
            self.table.viewport().update()

        specs = [
            (
                "geometry",
                lambda: bytes(self.saveGeometry().toBase64()).decode("ascii"),
                set_geometry,
            ),
            (
                "splitter_state",
                lambda: bytes(self._splitter.saveState().toBase64()).decode("ascii"),
                set_splitter_state,
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
                "reopen_last",
                self.reopen_last_action.isChecked,
                lambda v: self.reopen_last_action.setChecked(bool(v)),
            ),
            (
                "autosave",
                self.autosave_action.isChecked,
                lambda v: self.autosave_action.setChecked(bool(v)),
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
            ("recent_files", lambda: self._recent, set_recent),
            ("watch", lambda: self._watch_pattern, set_watch),
            ("collapse", self.collapse_action.isChecked, set_collapse),
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
                lambda: self._max_rows,
                set_max_rows,
            ),
            (
                "show_process",
                self.process_action.isChecked,
                lambda v: self.process_action.setChecked(bool(v)),
            ),
            ("wrap", lambda: self.log_delegate.wrap, set_wrap),
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
        self._want_stream = True
        self._last_time = ""
        self._reconnect_serial = self.device_box.currentData()
        self._start_reader(self._reconnect_serial)
        if self.process_action.isChecked():
            self._refresh_process_map()

    def _start_reader(self, serial, since_time=None, sess=None) -> None:
        sess = sess if sess is not None else self._active
        buffers = [name for name, act in self._buffer_actions.items() if act.isChecked()]
        tail = next((c for c, a in self._tail_actions.items() if a.isChecked()), 0)
        reader = AdbReader(serial=serial, buffers=buffers or None, tail=tail, since_time=since_time)
        reader.batch_ready.connect(lambda e, x=sess: self._on_batch(x, e))
        reader.error.connect(self.on_error)
        reader.stream_ended.connect(lambda x=sess: self._on_stream_ended(x))
        reader.start()
        sess.reader = reader
        sess.serial = serial or ""
        sess.paused = False
        sess.pause_buffer = []
        self._set_tab_label(sess)
        if sess is self._active:
            # Lock device selection while streaming; switching needs Stop first.
            self.device_box.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.pause_btn.setEnabled(True)
            self.pause_btn.setText("Pause")
            self._update_package_enabled()
        self.statusBar().showMessage(f"Streaming adb logcat ({serial or 'default'})…")

    def stop(self) -> None:
        sess = self._active
        sess.want_stream = False
        sess.reconnect_timer.stop()
        if sess.reader:
            sess.reader.stop()
            sess.reader = None
        sess.paused = False
        sess.pause_buffer = []
        self.refresh_btn.setEnabled(True)
        self.device_box.setEnabled(bool(self.devctl.devices))
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("Pause")
        self._update_start_enabled()
        self._set_tab_label(sess)
        self.statusBar().showMessage("Stopped.")

    def on_batch(self, entries) -> None:
        self._on_batch(self._active, entries)  # pause-flush path (active tab)

    def _on_process_toggled(self, checked: bool) -> None:
        """Show/hide the process-name column; refresh the PID->name map when on.
        (Persisted on close, like the other View toggles — no save here so it is
        safe to fire during settings load.)"""
        self.log_delegate.show_process = bool(checked)
        self.table.viewport().update()
        if checked:
            self._refresh_process_map()

    def _refresh_process_map(self) -> None:
        """One-shot `adb shell ps` snapshot for the active device, merged into the
        model so already-running processes get named (new ones come from the log)."""
        serial = self._current_serial()
        if serial is None:
            return
        names = self._run_adb(
            lambda: list_process_map(serial),
            missing_msg="adb not found.",
            error_prefix="Could not read process list",
            report=self.statusBar().showMessage,
        )
        if names:
            self.model.merge_process_names(names)

    def _on_batch(self, sess, entries) -> None:
        for entry in reversed(entries):
            if entry.time:  # newest real timestamp for this tab's reconnect resume
                sess.last_time = entry.time
                break
        self._autosave(entries)
        hits = self._watch_hits(entries)
        if hits:
            self._notify_watch(hits[-1])
        active = sess is self._active
        if sess.paused:
            sess.pause_buffer.extend(entries)
            if active:
                self.statusBar().showMessage(f"Paused — {len(sess.pause_buffer)} line(s) buffered.")
            return
        was_at_bottom = False
        if active:
            sb = self.table.verticalScrollBar()
            was_at_bottom = sb.value() >= sb.maximum() - 4
        sess.model.append_entries(entries)
        if active and self.devctl.filtering:
            self._track_new_pids(entries)
        if active and self.follow_check.isChecked() and was_at_bottom:
            self.table.scrollToBottom()

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._paused:
            self.pause_btn.setText("Resume")
            self.statusBar().showMessage("Paused — capturing continues; new lines buffer.")
        else:
            buffered = self._pause_buffer
            self._pause_buffer = []
            self.pause_btn.setText("Pause")
            if buffered:
                self.on_batch(buffered)  # flush in arrival order now that we are live
            self.statusBar().showMessage("Resumed.")

    def _on_stream_ended(self, sess) -> None:
        # The reader ended without a user Stop -> the device dropped. Poll for it to
        # come back and resume from the last timestamp (auto-reconnect).
        if not sess.want_stream:
            return
        sess.reader = None
        self._set_tab_label(sess)
        if sess is self._active:
            self.statusBar().showMessage("Device disconnected — waiting to reconnect…")
        sess.reconnect_timer.start()

    def _try_reconnect(self, sess=None) -> None:
        sess = sess if sess is not None else self._active
        if not sess.want_stream:
            sess.reconnect_timer.stop()
            return
        try:
            devices = list_devices()
        except Exception:
            return  # adb hiccup; keep polling
        if is_serial_streamable(devices, sess.reconnect_serial):
            sess.reconnect_timer.stop()
            if sess is self._active:
                self.statusBar().showMessage("Device back — reconnecting…")
            self._start_reader(sess.reconnect_serial, since_time=sess.last_time or None, sess=sess)

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
