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

from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QMimeData,
    QStandardPaths,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QColorDialog,
    QDialog,
    QFileDialog,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QProgressDialog,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from zlog.adb.connect import connect as adb_connect
from zlog.adb.devices import list_devices
from zlog.adb.packages import clear_logcat
from zlog.adb.processes import list_process_map
from zlog.adb.reader import AdbReader
from zlog.adb.snapshot import capture_dumpsys
from zlog.core.anchor import pick_anchor
from zlog.core.applog import get_logger
from zlog.core.autosave import AUTOSAVE_CAP, rotate_path, should_rotate
from zlog.core.bundle import make_bundle, parse_bundle
from zlog.core.density import DEFAULT_DENSITY, DENSITY_NAMES, density_pad
from zlog.core.devices import (
    Device,
    is_connect_ok,
    is_local_source,
    is_serial_streamable,
    local_device,
)
from zlog.core.diff import diff_logs, line_key
from zlog.core.export import to_html, to_markdown, to_messages
from zlog.core.heat import heat_marks
from zlog.core.highlight_rules import normalize_rules
from zlog.core.histogram import bucketize
from zlog.core.history import normalize_history, push_history
from zlog.core.incidents import format_incident_summary
from zlog.core.jank import jank_summary
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
from zlog.core.query import parse_query, remove_span
from zlog.core.redact import redact_entries
from zlog.core.search import compile_matcher
from zlog.core.session import entries_to_text, text_to_entries
from zlog.core.settings import DEFAULTS, load_settings, save_settings
from zlog.core.sparkline import error_rate_sparkline
from zlog.core.summary import format_level_summary, tag_counts
from zlog.core.timefmt import first_at_or_after, parse_logcat_time, parse_time_of_day
from zlog.ui.build import build_layout, build_widgets
from zlog.ui.capture_controller import CaptureController
from zlog.ui.device_controller import DeviceController
from zlog.ui.file_loader import FileLoader
from zlog.ui.highlight_rules_dialog import HighlightRulesDialog
from zlog.ui.log_session import LogSession
from zlog.ui.menus import build_menus
from zlog.ui.preset_dialog import PresetDialog
from zlog.ui.settings_dialog import SettingsDialog
from zlog.ui.sticky_header import StickyHeader
from zlog.ui.theme import THEMES, build_stylesheet
from zlog.winlog.dbwin_reader import is_supported  # cheap platform check, no Win32 import

_log = get_logger()


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
        self._font_family = ""  # chosen log font family ("" = the LOG_FONT_FAMILIES chain)
        self._density = DEFAULT_DENSITY  # row-padding preset (see core/density.py)
        self._max_rows = 0  # ring-buffer cap (0 = unlimited), any value
        self._adb_path_setting = ""  # explicit adb path ("" = use "adb" from PATH)
        self._query_package = ""  # effective proc: value last mirrored into the package box
        self._isolate_prev_query: str | None = None  # saved query while isolated (None = not)
        self._syncing_level = False  # guard: programmatic level_box sets skip the query mirror
        self._history: list[str] = []  # recent query-bar entries
        self._recent: list[str] = []  # recently opened/saved .log paths
        self._autosave_cap = AUTOSAVE_CAP  # bytes before the autosave file rolls over
        self._watch = None  # compiled substring matcher, or None
        self._watch_pattern = ""
        self._extract_patterns = []  # user regex named-group extractors (see core.extract)
        # Owns reader attach/detach for every capture kind (see CaptureController);
        # `capture.extra_readers` holds the merged-view / DBWIN companions.
        self.capture = CaptureController(
            self._on_batch, self.on_error, self._on_stream_ended, parent=self
        )
        self._last_launch = None  # (exe, args, cwd) prefilled into the Launch App dialog
        self._active_preset_name = None  # the applied preset the Save/Update button targets
        self._watch_last = 0.0  # monotonic time of last notification (throttle)
        self._tray = None  # lazily-created system-tray icon
        self._sessions: list[LogSession] = []  # capture tabs; re-rooted via properties
        self._active_index = 0
        self._heat_timer = QTimer(self)  # debounce heat-mark recompute
        self._heat_timer.setSingleShot(True)
        self._heat_timer.setInterval(400)
        self._heat_timer.timeout.connect(self._recompute_heat)
        self._histogram_timer = QTimer(self)  # debounce timeline-band rebuild
        self._histogram_timer.setSingleShot(True)
        self._histogram_timer.setInterval(250)
        self._histogram_timer.timeout.connect(self._rebuild_histogram)
        # Debounce the status-bar counts/sparkline recompute: a fast buffer dump
        # fires row signals thousands of times, and level_counts() is O(visible)
        # when filtered — recomputing per batch would be O(n^2) and freeze the UI.
        self._counts_timer = QTimer(self)
        self._counts_timer.setSingleShot(True)
        self._counts_timer.setInterval(150)
        self._counts_timer.timeout.connect(self._update_counts)
        # Coalesce the follow auto-scroll to once per burst instead of per batch.
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(80)
        self._scroll_timer.timeout.connect(self._do_follow_scroll)
        # Set right before a selection change's own "scroll the row into view"
        # side effect, so that scroll isn't mistaken for the user manually
        # scrolling back to the tail (see _maybe_resume_follow_on_scroll).
        self._suppress_next_scroll_clear = False
        # Coalesce query-bar typing onto one apply per pause instead of one
        # full re-filter per keystroke (see debounce-query-filter.md).
        self._query_timer = QTimer(self)
        self._query_timer.setSingleShot(True)
        self._query_timer.setInterval(150)
        self._query_timer.timeout.connect(self._apply_query)
        # Wrap mode sizes only the on-screen rows to their content (O(visible)); a
        # short timer coalesces inserts/scrolls so a fast dump never re-measures
        # the whole model (that was O(n^2) with ResizeToContents and froze Start).
        self._wrap_timer = QTimer(self)
        self._wrap_timer.setSingleShot(True)
        self._wrap_timer.setInterval(60)
        self._wrap_timer.timeout.connect(self._fit_visible_rows)
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
        self._refresh_save_update_button()  # initial Save/Update label from restored state
        self._maybe_reopen_last()
        self._load_plugins()

    # --- active-session re-rooting (tabs) ----------------------------------
    def _make_session(self) -> LogSession:
        sess = LogSession(self)
        self._wire_session_signals(sess)
        return sess

    def _wire_session_signals(self, sess) -> None:
        sess.model.rowsInserted.connect(self._schedule_counts)
        sess.model.modelReset.connect(self._schedule_counts)
        sess.model.rowsInserted.connect(self._schedule_histogram)
        sess.model.modelReset.connect(self._schedule_histogram)
        sess.model.rowsRemoved.connect(self._schedule_histogram)
        for sig in (
            sess.proxy.rowsInserted,
            sess.proxy.rowsRemoved,
            sess.proxy.modelReset,
            sess.proxy.layoutChanged,
        ):
            sig.connect(self._schedule_heat)
            sig.connect(self._update_placeholder)
            sig.connect(self._schedule_counts)
            sig.connect(self._schedule_wrap_fit)
        sess.reconnect_timer.timeout.connect(lambda s=sess: self._try_reconnect(s))

    # --- tabs --------------------------------------------------------------
    def _rebind_selection(self) -> None:
        self.table.selectionModel().currentChanged.connect(self._update_detail)
        self.table.selectionModel().currentChanged.connect(self._arm_scroll_clear_suppression)
        self.table.selectionModel().selectionChanged.connect(self._arm_scroll_clear_suppression)
        self.table.selectionModel().currentChanged.connect(self._update_sticky)

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
        # A saved "restore" query from another tab must never leak into this
        # one's "Show All".
        self._clear_isolate_state()
        # The session query carries the level: token, so it drives the dropdown +
        # proxy via _apply_query — no separate level_box set needed.
        self._set_query_text(sess.query)

    def _set_tab_label(self, sess) -> None:
        if sess not in self._sessions:
            return
        i = self._sessions.index(sess)
        if sess.reader is not None:  # streaming wins over any loaded-file title
            name = sess.stream_label or sess.serial or "Device"
            self.tab_bar.setTabText(i, f"\u25cf {name}")
            self.tab_bar.setTabToolTip(i, name)
            return
        name = sess.title or sess.serial or "Device"
        label = name if len(name) <= 22 else name[:21] + "\u2026"
        self.tab_bar.setTabText(i, label)
        self.tab_bar.setTabToolTip(i, sess.title or sess.serial or "")

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

    def _clear_active_view(self) -> None:
        """Clear button: empty the active tab's view and drop a loaded-file label
        so the tab no longer claims to hold that file (and becomes reusable)."""
        self.model.clear()
        if self._active.title:
            self._active.title = ""
            self._set_tab_label(self._active)

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
        """Create the model/proxy/view and every toolbar widget (see zlog.ui.build)."""
        build_widgets(self)

    def _build_layout(self) -> None:
        """Arrange the widgets into the window (see zlog.ui.build)."""
        build_layout(self)

    def _build_menus(self) -> None:
        """Build the File and View menus (see zlog.ui.menus)."""
        build_menus(self)

    def _open_log_folder(self) -> None:
        """Reveal the folder holding zlog.log (the self-diagnostics log), so a user
        can grab it when reporting a bug."""
        folder = str(self._settings_path().parent)
        _log.info("Opening log folder: %s", folder)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _connect_signals(self) -> None:
        """Wire toolbar/model/proxy signals to their slots (menu actions wire
        themselves in _build_menus)."""
        self.refresh_btn.clicked.connect(self.refresh_devices)
        self.table.verticalScrollBar().valueChanged.connect(self._schedule_wrap_fit)
        # A width change re-flows wrapped rows, so re-fit the visible ones (debounced
        # via _wrap_timer; a no-op when wrap is off) — see wrap-refit-on-resize.md.
        self.table.resized.connect(self._schedule_wrap_fit)
        # Sticky header: pin the anchor row while scrolling (see core.anchor).
        self.sticky_header = StickyHeader(self.table, self.log_delegate)
        self.sticky_header.setEnabled(False)  # off until the View toggle turns it on
        self.sticky_header.clicked.connect(self._jump_to_sticky)
        self._sticky_row = -1  # the pinned proxy row (-1 = none)
        self.table.verticalScrollBar().valueChanged.connect(self._update_sticky)
        self.table.resized.connect(self._update_sticky)
        self.tab_bar.currentChanged.connect(self._switch_tab)
        self.tab_bar.tabCloseRequested.connect(self._close_tab)
        self.presets_list.itemActivated.connect(self._on_preset_activated)
        self.presets_list.customContextMenuRequested.connect(self._show_presets_menu)
        self.save_update_btn.clicked.connect(self._save_or_update_active)
        self.query.textChanged.connect(self._on_query_changed_for_preset)
        self.presets_list.currentRowChanged.connect(self._update_preset_preview)
        self.to_top_btn.clicked.connect(self.table.scrollToTop)
        self.to_latest_btn.clicked.connect(self._jump_to_latest)
        self.table.verticalScrollBar().valueChanged.connect(self._maybe_resume_follow_on_scroll)
        self.device_box.currentIndexChanged.connect(self._update_start_enabled)
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.clear_btn.clicked.connect(self._clear_active_view)
        self.clear_device_btn.clicked.connect(self._clear_device_buffer)
        self.connect_btn.clicked.connect(self._connect_over_wifi)
        self.pause_btn.clicked.connect(self._toggle_pause)
        # Ctrl+wheel over the log or detail zooms (handled in eventFilter);
        # filter the viewports, since that is where wheel events are delivered.
        self.table.viewport().installEventFilter(self)
        self.detail.viewport().installEventFilter(self)
        self.load_pkgs_btn.clicked.connect(self.load_packages)
        self.apply_pkg_btn.clicked.connect(self.apply_package_filter)
        self.clear_pkg_btn.clicked.connect(self.clear_package_filter)
        self.package_box.lineEdit().returnPressed.connect(self.apply_package_filter)
        self.package_box.textActivated.connect(self.apply_package_filter)  # pick from dropdown
        self.level_box.currentIndexChanged.connect(self._on_level_box_changed)
        self.search.textChanged.connect(self._apply_search)
        self.query.textChanged.connect(self._schedule_query_apply)
        self.query.textChanged.connect(self.chip_bar.set_query)
        self.query.returnPressed.connect(self._commit_query_history)
        self.exclude.textChanged.connect(self._apply_search)
        self.match_next_btn.clicked.connect(lambda: self._goto_match(1))
        self.match_prev_btn.clicked.connect(lambda: self._goto_match(-1))
        QShortcut(QKeySequence("F3"), self, activated=lambda: self._goto_match(1))
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self._open_command_palette)
        QShortcut(QKeySequence("Shift+F3"), self, activated=lambda: self._goto_match(-1))
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self._open_goto)
        QShortcut(QKeySequence("Alt+Down"), self, activated=lambda: self._goto_same("tag", 1))
        QShortcut(QKeySequence("Alt+Up"), self, activated=lambda: self._goto_same("tag", -1))
        QShortcut(QKeySequence("Ctrl+Alt+Down"), self, activated=lambda: self._goto_same("pid", 1))
        QShortcut(QKeySequence("Ctrl+Alt+Up"), self, activated=lambda: self._goto_same("pid", -1))
        self.regex_check.toggled.connect(self._apply_search)
        self.case_check.toggled.connect(self._apply_search)
        self.search_mode_box.currentIndexChanged.connect(self._apply_search)
        self.clear_filters_btn.clicked.connect(self.clear_filters)
        self._rebind_selection()

    # --- devices -----------------------------------------------------------
    def _adb_path(self) -> str:
        """The adb executable to invoke — the Settings override, or plain "adb"
        (resolved via PATH) when unset."""
        return self._adb_path_setting or "adb"

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
            lambda: list_devices(self._adb_path()),
            missing_msg="adb not found — install Android platform-tools and add it to PATH.",
            error_prefix="Could not list devices",
            report=self._show_device_error,
        )
        if devices is None:
            return
        self._populate_devices(devices)

    def _connect_over_wifi(self) -> None:
        host_port, ok = QInputDialog.getText(
            self, "Connect over Wi-Fi", "Device address (host or host:port):"
        )
        host_port = host_port.strip()
        if not ok or not host_port:
            return
        message = self._run_adb(
            lambda: adb_connect(host_port, self._adb_path()),
            missing_msg="adb not found — install Android platform-tools and add it to PATH.",
            error_prefix="Could not connect",
            report=self.statusBar().showMessage,
        )
        if message is None:
            return
        self.statusBar().showMessage(message)
        if is_connect_ok(message):
            self.refresh_devices()

    def _populate_devices(self, devices: list[Device]) -> None:
        """Fill the picker from a device list (also called by the run-zlog driver
        with fake devices, so it stays free of subprocess calls)."""
        # "This PC" rides the same picker + Start flow as a device (see
        # local-source-in-device-box.md); it goes first so it's visible when no
        # phone is attached — which is the main case for capturing debug output.
        if is_supported():
            devices = [local_device(), *devices]
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
        real = sum(1 for d in devices if not d.is_local)  # "This PC" isn't a device
        self.statusBar().showMessage(f"{real} device(s) found.")

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
        self._update_adb_only_controls()

    def _update_adb_only_controls(self) -> None:
        """Grey out the actions that only mean something for a real device, so
        picking "This PC" can't invoke adb. (The package box stays enabled — it
        filters the log by process name, which works for debug output too.)"""
        adb = not is_local_source(self.device_box.currentData())
        self.clear_device_btn.setEnabled(adb)
        self.connect_btn.setEnabled(adb)
        self.dumpsys_act.setEnabled(adb)

    def _update_package_enabled(self) -> None:
        # The package selector is log-driven (proc: filter), so it's always
        # usable — no live device required; Load just reflects the current log.
        for w in (self.package_box, self.load_pkgs_btn, self.apply_pkg_btn, self.clear_pkg_btn):
            w.setEnabled(True)

    # --- package selector (log-driven; syncs with the proc: query token) ----
    def load_packages(self) -> None:
        """Fill the dropdown with the process/package names the current log has
        parsed — no adb, so it works on an opened offline log too."""
        names = self.model.process_names()
        current = self.package_box.currentText()
        self.package_box.blockSignals(True)  # repopulating must not self-apply
        self.package_box.clear()
        self.package_box.addItems(names)
        self.package_box.setEditText(current)
        self.package_box.blockSignals(False)
        self.statusBar().showMessage(f"{len(names)} package(s) from the log.")

    def apply_package_filter(self) -> None:
        """Filter to the chosen package via a proc: query token (matches the log's
        resolved process name). Empty text clears the package filter."""
        package = self.package_box.currentText().strip()
        if package:
            self._add_query_token(f"proc:{package}")
        else:
            self.clear_package_filter()

    def clear_package_filter(self) -> None:
        self._remove_query_token("proc")
        self.package_box.setEditText("")
        self.statusBar().showMessage("Package filter cleared.")

    def clear_filters(self) -> None:
        """Reset every filter to 'show everything' without touching the log."""
        # The query bar owns every filter incl. the level floor, so clearing it
        # (via _apply_query) resets level/tag/search/exclude/package together.
        self._clear_isolate_state()  # don't resurrect a query the user just cleared
        self._set_query_text("")
        self._active_preset_name = None  # detach any applied preset (back to Save)
        self._refresh_save_update_button()
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
            self._set_query_text(new_text)

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
        self._active_preset_name = name  # now editing that saved filter
        self._refresh_save_update_button()
        self._save_settings()
        self.statusBar().showMessage(f"Saved preset {name!r}.")

    # --- Save/Update filter button ----------------------------------------
    def _active_preset(self) -> dict | None:
        """The applied preset the Save/Update button targets, re-checked against
        the current presets so a deleted/renamed name falls back to None."""
        if not self._active_preset_name:
            return None
        return next((p for p in self._presets if p["name"] == self._active_preset_name), None)

    def _refresh_save_update_button(self) -> None:
        """Toggle the filter-row button between Save (unsaved filter) and Update
        (a saved filter is applied)."""
        preset = self._active_preset()
        if preset is None:
            self.save_update_btn.setText("Save filter…")
            self.save_update_btn.setToolTip("Save the current filter as a new preset")
            self.save_update_btn.setEnabled(bool(self.query.text().strip()))
        else:
            name = preset["name"]
            label = name if len(name) <= 18 else name[:17] + "…"
            self.save_update_btn.setText(f"Update {label}")
            self.save_update_btn.setToolTip(f"Overwrite “{name}” with the current filter")
            self.save_update_btn.setEnabled(True)

    def _save_or_update_active(self) -> None:
        """Filter-row button: update the applied preset, else save a new one."""
        preset = self._active_preset()
        if preset is None:
            self.save_current_preset()
        else:
            self._update_preset_to_current(preset)

    def _on_query_changed_for_preset(self, text: str) -> None:
        """Emptying the query bar detaches the applied preset (back to Save); a
        non-empty edit keeps it (so Update captures the edits). Only user edits
        reach here — _set_query_text blocks signals during programmatic changes."""
        if not text.strip():
            self._active_preset_name = None
        self._refresh_save_update_button()

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
        self._set_query_text(text)  # drives the dropdown + proxy (signals blocked)
        # Set *after* _set_query_text so its (blocked) textChanged can't clear this,
        # and so the button now offers to Update this preset.
        self._active_preset_name = preset.get("name") or None
        self._refresh_save_update_button()
        self.statusBar().showMessage(f"Applied preset {preset.get('name', '')!r}.")

    def _delete_preset(self, name: str) -> None:
        self._presets = remove_preset(self._presets, name)
        self._rebuild_presets_menu()
        self._refresh_save_update_button()  # if the active preset was deleted -> Save
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

    def _delete_selected_preset(self, preset: dict | None = None) -> None:
        preset = preset if preset is not None else self._selected_preset()
        if preset is not None:
            self._delete_preset(preset["name"])

    # --- Saved-filter right-click menu ------------------------------------
    def _preset_at(self, pos) -> dict | None:
        """The preset under a right-click position (falls back to the selection)."""
        item = self.presets_list.itemAt(pos) or self.presets_list.currentItem()
        if item is None:
            return None
        name = item.data(Qt.UserRole)
        return next((p for p in self._presets if p["name"] == name), None)

    def _show_presets_menu(self, pos) -> None:
        preset = self._preset_at(pos)
        menu = QMenu(self)
        if preset is not None:
            # On a preset: manage that one. Clone duplicates *it*; Add (from the
            # current filter) lives on the filter-row Save button + empty-space menu.
            menu.addAction("Apply", lambda: self._apply_preset(preset))
            menu.addSeparator()
            menu.addAction("Clone…", lambda: self._clone_preset(preset))
            menu.addAction("Edit…", lambda: self._edit_preset(preset))
            menu.addAction("Rename…", lambda: self._rename_preset(preset))
            menu.addAction("Delete", lambda: self._delete_selected_preset(preset))
        else:
            menu.addAction("Add…", self._add_preset)  # new preset from the current filter
        menu.exec(self.presets_list.mapToGlobal(pos))

    def _preset_from_query(self, name: str, query: str, base: dict | None = None) -> dict:
        """Build a preset dict from a raw query string (source of truth), parsing it
        to fill the decomposed summary/legacy fields. `case` carries over from `base`
        (Edit) or the current toggle (Add)."""
        spec = parse_query(query)
        return make_preset(
            name,
            min_level=spec.level or "V",
            search=spec.search,
            regex=spec.regex,
            case=bool(base["case"]) if base else self.case_check.isChecked(),
            package=spec.package,
            query=query,
        )

    def _add_preset(self) -> None:
        """Create a new preset from a Name+Query editor, seeded with the current filter."""
        dlg = PresetDialog("Add saved filter", query=self.query.text(), parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        name, query = dlg.get_values()
        if not name:
            return
        self._presets = upsert_preset(self._presets, self._preset_from_query(name, query))
        self._rebuild_presets_menu()
        self._refresh_save_update_button()
        self._save_settings()
        self.statusBar().showMessage(f"Saved preset {name!r}.")

    def _clone_preset(self, preset: dict) -> None:
        """Duplicate a saved filter: the editor is seeded with its query and a
        '‹name› copy' name so you can save a variant without touching the original."""
        dlg = PresetDialog(
            "Clone saved filter",
            name=f"{preset['name']} copy",
            query=preset.get("query", ""),
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        name, query = dlg.get_values()
        if not name:
            return
        # Carry the source's case toggle; a distinct name makes it a new preset.
        clone = self._preset_from_query(name, query, base=preset)
        self._presets = upsert_preset(self._presets, clone)
        self._rebuild_presets_menu()
        self._refresh_save_update_button()
        self._save_settings()
        self.statusBar().showMessage(f"Cloned to {name!r}.")

    def _edit_preset(self, preset: dict) -> None:
        """Edit a saved filter's query (name stays — use Rename to change it)."""
        dlg = PresetDialog(
            "Edit saved filter",
            name=preset["name"],
            query=preset.get("query", ""),
            name_editable=False,
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        _name, query = dlg.get_values()
        self._presets = upsert_preset(
            self._presets, self._preset_from_query(preset["name"], query, base=preset)
        )
        self._rebuild_presets_menu()
        self._refresh_save_update_button()  # active preset (same name) keeps tracking
        self._save_settings()
        self.statusBar().showMessage(f"Updated preset {preset['name']!r}.")

    def _selected_preset(self) -> dict | None:
        item = self.presets_list.currentItem()
        if item is None:
            return None
        name = item.data(Qt.UserRole)
        return next((p for p in self._presets if p["name"] == name), None)

    def _update_preset_preview(self, *args) -> None:
        preset = self._selected_preset()
        self.preset_preview.setText(preset_summary(preset) if preset else "")

    def _update_preset_to_current(self, preset: dict | None = None) -> None:
        preset = preset if preset is not None else self._selected_preset()
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
        self._active_preset_name = preset["name"]  # stays the applied filter
        self._refresh_save_update_button()
        self._save_settings()
        self.statusBar().showMessage(f"Updated {preset['name']!r} to the current filter.")

    def _rename_preset(self, preset: dict | None = None) -> None:
        preset = preset if preset is not None else self._selected_preset()
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
        if self._active_preset_name == preset["name"]:
            self._active_preset_name = name  # keep the applied filter tracked
        self._rebuild_presets_menu()
        self._refresh_save_update_button()
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

    def _set_query_text(self, text: str) -> None:
        """Set the query bar's text and apply the filter immediately, bypassing
        the typing debounce — for discrete actions (settings restore, presets,
        context-menu tokens, level-dropdown sync, tab switches), not keystrokes.
        `query.textChanged` would otherwise only schedule a debounced apply,
        the same as if the user had typed it."""
        self.query.blockSignals(True)
        self.query.setText(text)
        self.query.blockSignals(False)
        self.chip_bar.set_query(text)  # textChanged is blocked above, so refresh chips here
        self._apply_query()

    def _remove_query_span(self, start: int, end: int) -> None:
        """A filter chip's × was clicked: slice that token span out of the query."""
        self._set_query_text(remove_span(self.query.text(), start, end))

    def _completion_context(self):
        """Live values for the query-bar autocomplete: (tags, procs, pids), each
        capped so the popup stays snappy on huge captures."""
        return (
            self.model.known_tags()[:300],
            self.model.process_names()[:300],
            self.model.known_pids()[:300],
        )

    def _apply_query(self) -> None:
        """Parse the single query bar and drive the (hidden) filter widgets +
        proxy gates. This is the one place filtering is applied in the new UI."""
        self._query_timer.stop()  # in case this was called directly, not via the timer
        spec = parse_query(self.query.text())
        case = self.case_check.isChecked()
        # ~9 proxy setters below each carry their own invalidate() — batching
        # them collapses what would be 9 full re-filter passes into 1 per apply.
        with self.proxy.batch_update():
            if spec.levels:
                self.proxy.set_levels(set(spec.levels))  # exact level set
            else:
                self.proxy.set_levels(None)
                level = spec.level or "V"  # query is the source of truth; no token = V
                self._set_level_box(level)  # mirror into the dropdown (guarded)
                self.proxy.set_min_level(level)
            self.proxy.set_tag(spec.tag)
            self.proxy.set_query_pids(set(spec.pids) if spec.pids else None)
            # The package box maps to the process-name filter; `package:` is now
            # an alias of `proc:` (log-driven, no adb — see package-selector-from-log.md).
            effective_proc = spec.process or spec.package
            self.proxy.set_proc(effective_proc)
            self.proxy.set_exclude_pids(set(spec.exclude_pids) if spec.exclude_pids else None)
            self.proxy.set_exclude_proc(spec.exclude_process)
            ex_pat = "|".join(re.escape(t) for t in spec.excludes)
            ex_ok = self.proxy.set_exclude(ex_pat, bool(spec.excludes), case)
            since_time = parse_time_of_day(spec.since) if spec.since else None
            until_time = parse_time_of_day(spec.until) if spec.until else None
            time_ok = (not spec.since or since_time is not None) and (
                not spec.until or until_time is not None
            )
            if time_ok:
                self.proxy.set_time_range(since_time, until_time)
            self.proxy.set_devices(set(spec.devices) if spec.devices else None)
            self.proxy.set_exclude_devices(
                set(spec.exclude_devices) if spec.exclude_devices else None
            )
            self.regex_check.setChecked(spec.regex)  # -> _apply_search
            self.search.setText(spec.search)  # -> _apply_search (search + highlight)
            # Mirror the effective process filter into the package box (the other
            # half of the two-way sync). setEditText emits no activation signal, so
            # this can't loop back into apply_package_filter.
            if effective_proc != self._query_package:
                self._query_package = effective_proc
                self.package_box.setEditText(effective_proc)
        search_ok = True
        try:
            compile_matcher(spec.search, spec.regex, case)
        except re.error:
            search_ok = False
        good = search_ok and ex_ok and time_ok
        self.query.setStyleSheet(
            "" if good else f"QLineEdit {{ background-color: {self._search_error_color}; }}"
        )

    def _schedule_query_apply(self, *_args) -> None:
        """Coalesce query-bar typing onto a short timer instead of re-filtering
        on every keystroke — see debounce-query-filter.md."""
        self._query_timer.start()
        # Only real keystrokes reach this slot (_set_query_text blocks signals
        # around its own writes), so a manual edit here means the isolated
        # query is no longer intact — drop the saved "restore" state rather
        # than let a later "Show All" discard the edit.
        self._clear_isolate_state()

    def _commit_query_history(self) -> None:
        """Remember the current query (on Enter) for the completer; persist it."""
        self._apply_query()  # flush a pending debounce so Enter never feels delayed
        text = self.query.text().strip()
        if not text:
            return
        self._history = push_history(self._history, text)  # persisted; kept for future use
        self._save_settings()

    def _on_case_toggled(self, checked: bool) -> None:
        self.case_check.setChecked(checked)
        self._apply_query()

    def _on_highlight_toggled(self, checked: bool) -> None:
        self.search_mode_box.setCurrentIndex(1 if checked else 0)
        self._apply_query()

    def _on_collapse_toggled(self, checked: bool) -> None:
        self.proxy.set_collapse(checked)
        self.log_delegate.collapse = checked  # show/hide the ×N duplicate badge
        self.table.viewport().update()

    def _on_fold_toggled(self, checked: bool) -> None:
        if checked:
            self.model.fold_all()
        else:
            self.model.unfold_all()
        self.proxy.invalidate()  # re-run the frame-hidden gate over all rows

    def _on_fold_toggle_requested(self, source_row: int) -> None:
        """Double-click on a stack-trace header folds/unfolds just that trace."""
        self.model.toggle_fold(source_row)
        self.proxy.invalidate()

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

    def _select_proxy_row(self, row: int) -> None:
        """Select and scroll to a row by its visible (proxy) index."""
        index = self.proxy.index(row, 0)
        self.table.setCurrentIndex(index)
        self.table.selectRow(row)
        self.table.scrollTo(index)

    def _open_goto(self) -> None:
        """Ctrl+G: jump to a line number (1-based, into the visible rows) or a
        time-of-day (HH:MM:SS[.mmm], optionally prefixed "MM-DD ")."""
        total = self.proxy.rowCount()
        if total == 0:
            self.statusBar().showMessage("Nothing to jump to.")
            return
        text, ok = QInputDialog.getText(self, "Go to", "Line number, or time HH:MM:SS:")
        text = text.strip()
        if not ok or not text:
            return
        if text.isdigit():
            row = max(0, min(int(text), total) - 1)
            self._select_proxy_row(row)
            return
        target = parse_time_of_day(text)
        if target is None:
            self.statusBar().showMessage(f"Couldn't parse {text!r} as a line number or time.")
            return
        times = [
            self.model.entry_at(self.proxy.mapToSource(self.proxy.index(r, 0)).row()).time
            for r in range(total)
        ]
        row = first_at_or_after(times, target)
        self._select_proxy_row(row if row is not None else total - 1)

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

    def _goto_same(self, field: str, step: int) -> None:
        """Jump to the next/previous visible line whose `field` ("tag"/"pid")
        equals the selected line's, wrapping — same early-exit scan as
        _goto_severity but over an equality predicate instead of a rank."""
        self._goto_same_from(self.table.currentIndex(), field, step)

    def _goto_same_from(self, index, field: str, step: int) -> None:
        """Jump from `index` (a proxy index) to the next/prev visible line whose
        `field` matches it, wrapping. Used by both the shortcuts (from the
        current row) and the context menu (from the clicked row)."""
        if not index.isValid():
            return
        value = getattr(self.model.entry_at(self.proxy.mapToSource(index).row()), field)
        if not value:
            return
        n = self.proxy.rowCount()
        cur = index.row()
        forward = range(cur + 1, n) if step > 0 else range(cur - 1, -1, -1)
        wrap = range(n) if step > 0 else range(n - 1, -1, -1)
        for r in list(forward) + list(wrap):
            src = self.proxy.mapToSource(self.proxy.index(r, 0)).row()
            if getattr(self.model.entry_at(src), field) == value:
                self._select_proxy_row(r)
                return

    # --- bookmarks ---------------------------------------------------------
    def _toggle_bookmark(self) -> None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        self.model.toggle_bookmark(self.proxy.mapToSource(idx).row())

    # --- isolate -------------------------------------------------------------
    def _current_entry(self) -> LogEntry | None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.entry_at(self.proxy.mapToSource(idx).row())

    def _clear_isolate_state(self) -> None:
        self._isolate_prev_query = None
        self.isolate_action.setText("Isolate")

    def _toggle_isolate(self, entry: LogEntry | None) -> None:
        """Narrow to `entry`'s pid+tag, or restore the query active before the
        last isolate — see isolate-toggle.md for why this state resets on any
        real query-bar edit (_schedule_query_apply) rather than staying sticky."""
        if self._isolate_prev_query is not None:
            self._set_query_text(self._isolate_prev_query)
            self._isolate_prev_query = None
            self.isolate_action.setText("Isolate")
            return
        if entry is None or not entry.pid:
            return
        token = f"pid:{entry.pid}" + (f" tag:{entry.tag}" if entry.tag else "")
        self._isolate_prev_query = self.query.text()
        self._set_query_text(token)
        self.isolate_action.setText("Show All")

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

    def _rebuild_bookmarks_list(self) -> None:
        """Refresh the Bookmarks dock from the model (line + label/preview)."""
        self.bookmarks_list.clear()
        for src in self.model.bookmarked_rows():
            entry = self.model.entry_at(src)
            label = self.model.bookmark_label(src)
            preview = label or (entry.message[:60] if entry is not None else "")
            item = QListWidgetItem(f"line {src + 1}  •  {preview}")
            item.setData(Qt.UserRole, src)
            self.bookmarks_list.addItem(item)

    def _jump_to_bookmark_item(self, item) -> None:
        src = item.data(Qt.UserRole)
        if src is None:
            return
        proxy_row = self.proxy.mapFromSource(self.model.index(int(src), 0)).row()
        if proxy_row < 0:  # bookmark hidden by the current filter
            self.statusBar().showMessage("That bookmark is hidden by the current filter.")
            return
        index = self.proxy.index(proxy_row, 0)
        self.table.setCurrentIndex(index)
        self.table.selectRow(proxy_row)
        self.table.scrollTo(index)

    def _edit_bookmark_note(self) -> None:
        item = self.bookmarks_list.currentItem()
        if item is None:
            return
        src = int(item.data(Qt.UserRole))
        current = self.model.bookmark_label(src)
        text, ok = QInputDialog.getText(self, "Edit bookmark note", "Note:", text=current)
        if ok:
            self.model.set_bookmark_label(src, text.strip())

    def _remove_selected_bookmark(self) -> None:
        item = self.bookmarks_list.currentItem()
        if item is None:
            return
        self.model.toggle_bookmark(int(item.data(Qt.UserRole)))

    def _clear_bookmarks(self) -> None:
        self.model.clear_bookmarks()

    # --- crash/ANR navigation -----------------------------------------------
    def _goto_incident(self, step: int) -> None:
        rows = []
        for src in self.model.incident_rows():
            proxy_row = self.proxy.mapFromSource(self.model.index(src, 0)).row()
            if proxy_row >= 0:  # skip incidents hidden by the current filter
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

    # --- timeline histogram -----------------------------------------------
    def _on_histogram_toggled(self, checked: bool) -> None:
        self.histogram_bar.setVisible(bool(checked))
        if checked:
            self._rebuild_histogram()

    def _schedule_histogram(self, *args) -> None:
        if self.histogram_bar.isVisible():
            self._histogram_timer.start()

    def _rebuild_histogram(self) -> None:
        if not self.histogram_bar.isVisible():
            return
        entries = self.model.all_entries()
        times = [parse_logcat_time(e.time) for e in entries]
        levels = [e.level for e in entries]
        self.histogram_bar.set_data(bucketize(times, levels, self.histogram_bar.bucket_count()))

    # --- sticky header -----------------------------------------------------
    def _update_sticky(self, *args) -> None:
        """Recompute and reposition the pinned anchor row as the view scrolls."""
        if not self.sticky_header.isEnabled():  # gated by the View toggle
            self.sticky_header.set_index(None)
            self._sticky_row = -1
            return
        first_visible = self.table.rowAt(0)
        selected = self.table.currentIndex().row()
        bookmarks = []
        for src in self.model.bookmarked_rows():
            pr = self.proxy.mapFromSource(self.model.index(src, 0)).row()
            if pr >= 0:
                bookmarks.append(pr)
        anchor = pick_anchor(first_visible, selected, bookmarks)
        self._sticky_row = anchor if anchor is not None else -1
        self.sticky_header.set_index(self.proxy.index(anchor, 0) if anchor is not None else None)

    def _jump_to_sticky(self) -> None:
        if self._sticky_row >= 0:
            index = self.proxy.index(self._sticky_row, 0)
            self.table.setCurrentIndex(index)
            self.table.selectRow(self._sticky_row)
            self.table.scrollTo(index)

    def _on_sticky_toggled(self, checked: bool) -> None:
        # Enabled flag doubles as the on/off gate read by _update_sticky.
        self.sticky_header.setEnabled(bool(checked))
        self._update_sticky()

    def _seek_to_source_row(self, src: int) -> None:
        """Scroll/select the given source row (from a histogram-band click)."""
        proxy_row = self.proxy.mapFromSource(self.model.index(int(src), 0)).row()
        if proxy_row < 0:
            self.statusBar().showMessage("That point is hidden by the current filter.")
            return
        index = self.proxy.index(proxy_row, 0)
        self.table.setCurrentIndex(index)
        self.table.selectRow(proxy_row)
        self.table.scrollTo(index)

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

    def _capture_dumpsys(self) -> None:
        """Save a one-shot `adb shell dumpsys` snapshot for the current device."""
        serial = self._current_serial()
        if serial is None:
            self.statusBar().showMessage("Select a device first to capture dumpsys.")
            return
        section, ok = QInputDialog.getText(
            self,
            "Capture dumpsys",
            "Service (blank = everything, e.g. battery, meminfo, activity):",
        )
        if not ok:
            return
        self.statusBar().showMessage("Capturing dumpsys…")
        output = self._run_adb(
            lambda: capture_dumpsys(serial, section, self._adb_path()),
            missing_msg="adb not found.",
            error_prefix="Could not capture dumpsys",
            report=self.statusBar().showMessage,
        )
        if not output:
            return
        default = f"dumpsys-{section.strip() or 'all'}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save dumpsys", default, "Text files (*.txt);;All files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(output)
        except OSError as exc:
            self.statusBar().showMessage(f"Could not save: {exc}")
            return
        self.statusBar().showMessage(f"Saved dumpsys to {Path(path).name}.")

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
            self._set_query_text(f"tag:{rows[row][0]}")
            dlg.accept()

        table.cellDoubleClicked.connect(use)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("Double-click a tag to filter to it:"))
        layout.addWidget(table)
        dlg.exec()

    def _show_jank_summary(self) -> None:
        """Modal list of Choreographer jank by PID; double-click filters."""
        rows = jank_summary(self._filtered_entries())
        dlg = QDialog(self)
        dlg.setWindowTitle("Jank Summary")
        dlg.resize(360, 440)
        table = QTableWidget(len(rows), 3, dlg)
        table.setHorizontalHeaderLabels(["PID", "Events", "Frames Skipped"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i, (pid, events, total_frames) in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(pid))
            for col, value in ((1, events), (2, total_frames)):
                cell = QTableWidgetItem(str(value))
                cell.setTextAlignment(int(Qt.AlignRight | Qt.AlignVCenter))
                table.setItem(i, col, cell)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

        def use(row: int, _col: int) -> None:
            self._set_query_text(f"pid:{rows[row][0]}")
            dlg.accept()

        table.cellDoubleClicked.connect(use)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("Double-click a PID to filter to it:"))
        layout.addWidget(table)
        dlg.exec()

    def _show_highlight_rules_dialog(self) -> None:
        dlg = HighlightRulesDialog(self.model.highlight_rules(), parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.model.set_highlight_rules(normalize_rules(dlg.get_values()))
            self.table.viewport().update()

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
    def _make_log_font(self) -> QFont:
        """Build the log table's monospace font, honoring the chosen family
        (``_font_family``; "" = the built-in chain) and the zoom offset. A picked
        family is listed *before* the chain so a later-uninstalled family still
        falls back to a readable monospace instead of vanishing."""
        font = QFont()
        if self._font_family:
            font.setFamilies([self._font_family, *LOG_FONT_FAMILIES])
        else:
            font.setFamilies(LOG_FONT_FAMILIES)
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(max(6, min(28, BASE_FONT_PT + self._font_delta)))
        return font

    def _apply_font(self) -> None:
        size = max(6, min(28, BASE_FONT_PT + self._font_delta))
        self.table.setFont(self._make_log_font())
        # The detail pane keeps its default (proportional) family unless the user
        # picks a log font; only the size tracks zoom otherwise.
        detail_font = self.detail.font()
        if self._font_family:
            detail_font.setFamily(self._font_family)
        detail_font.setPointSize(size)
        self.detail.setFont(detail_font)
        self._apply_row_height()

    def _set_font_family(self, name: str) -> None:
        self._font_family = str(name or "")
        self._apply_font()

    def _available_log_fonts(self) -> list[str]:
        """Installed fixed-pitch families for the Settings font picker. Only
        monospace families are offered, so a pick can't break column alignment.
        The currently-chosen family is always included, even if this machine
        doesn't report it as fixed-pitch, so it stays selected in the dialog."""
        families = sorted(f for f in QFontDatabase.families() if QFontDatabase.isFixedPitch(f))
        if self._font_family and self._font_family not in families:
            families.append(self._font_family)
        return families

    def _apply_row_height(self) -> None:
        """Uniform one-line rows; when wrap is on, only the on-screen rows are grown
        to their full message (see _fit_visible_rows) so streaming never gets slow."""
        vh = self.table.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.Fixed)  # never ResizeToContents (O(n^2) on stream)
        fm = QFontMetrics(self.table.font())
        vh.setDefaultSectionSize(fm.height() + self.log_delegate.row_pad)
        if self.log_delegate.wrap:
            self._fit_visible_rows()  # grow the visible rows now
        else:
            # Reset any rows we grew back to one line (cheap: sizeHint is one line now).
            self.table.resizeRowsToContents()

    def _schedule_wrap_fit(self, *args) -> None:
        if self.log_delegate.wrap:
            self._wrap_timer.start()

    def _fit_visible_rows(self) -> None:
        """Size only the rows currently in the viewport to their content (O(visible))."""
        if not self.log_delegate.wrap:
            return
        n = self.proxy.rowCount()
        if n == 0:
            return
        vp_h = self.table.viewport().height()
        first = self.table.rowAt(0)
        last = self.table.rowAt(max(0, vp_h - 1))
        if first < 0:
            first = 0
        if last < 0:
            last = n - 1
        for r in range(max(0, first - 2), min(n, last + 3)):
            self.table.resizeRowToContents(r)

    def _zoom(self, step: int) -> None:
        self._font_delta = max(-4, min(12, self._font_delta + step))
        self._apply_font()

    def _reset_zoom(self) -> None:
        self._font_delta = 0
        self._apply_font()

    def _set_font_delta(self, n: int) -> None:
        self._font_delta = max(-4, min(12, int(n)))
        self._apply_font()

    def _set_density(self, name: str) -> None:
        """Apply a row-density preset (compact/default/comfortable): set the
        delegate's per-row padding and re-lay-out row heights."""
        self._density = name if name in DENSITY_NAMES else DEFAULT_DENSITY
        self.log_delegate.row_pad = density_pad(self._density)
        self._apply_row_height()
        self.table.viewport().update()

    # --- settings dialog ---------------------------------------------------
    def _collect_settings(self) -> dict:
        """Snapshot the current preference state for the Settings dialog."""
        time_mode = next((m for m, a in self._time_actions.items() if a.isChecked()), "absolute")
        tail = next((c for c, a in self._tail_actions.items() if a.isChecked()), 0)
        return {
            "theme": self._theme_name,
            "font_delta": self._font_delta,
            "font_family": self._font_family,
            "density": self._density,
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
            "line_numbers": self.log_delegate.line_numbers,
            "adb_path": self._adb_path_setting,
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
                ("Last 10,000", 10000),
            ],
            buffers=["main", "system", "crash", "radio", "events", "kernel"],
            fonts=self._available_log_fonts(),
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
        self._set_font_family(v["font_family"])
        self._set_font_delta(v["font_delta"])
        self._set_density(v["density"])
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
        self.log_delegate.line_numbers = bool(v["line_numbers"])
        self._apply_row_height()
        self.table.viewport().update()
        self._adb_path_setting = v["adb_path"]
        self._save_settings()

    def _clear_device_buffer(self) -> None:
        """Wipe the device's on-device logcat ring buffer (adb logcat -c)."""
        serial = self._current_serial()
        if serial is None:
            self.statusBar().showMessage("Select a device first.")
            return
        ok = self._run_adb(
            lambda: clear_logcat(serial, self._adb_path()),
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
            theme.inline_match,
        )
        self.histogram_bar.set_theme(theme.meta_text, theme.level_text["E"], theme.base)
        self.query.set_muted_color(theme.muted)  # autocomplete description color
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

    def _copy_html(self) -> None:
        entries = self._selected_entries()
        if not entries:
            return
        mime = QMimeData()
        mime.setHtml(to_html(entries))
        mime.setText(to_messages(entries))  # plain-text fallback for non-rich targets
        QApplication.clipboard().setMimeData(mime)
        self.statusBar().showMessage(f"Copied {len(entries)} line(s) as HTML.")

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
        self._set_query_text(
            " ".join(shlex.quote(t) if any(ch.isspace() for ch in t) else t for t in kept)
        )
        self.statusBar().showMessage(f"Filter \u2192 {token}")

    def _remove_query_token(self, key: str) -> None:
        """Drop every `key:...` token from the query bar (reapplies the filter)."""
        try:
            tokens = shlex.split(self.query.text())
        except ValueError:
            tokens = self.query.text().split()
        kept = [t for t in tokens if not t.startswith(key + ":")]
        self._set_query_text(
            " ".join(shlex.quote(t) if any(ch.isspace() for ch in t) else t for t in kept)
        )

    def _show_table_menu(self, pos) -> None:
        menu = QMenu(self.table)
        menu.addAction(self.copy_action)
        copy_md = menu.addAction("Copy as Markdown")
        copy_md.triggered.connect(self._copy_markdown)
        copy_msg = menu.addAction("Copy message only")
        copy_msg.triggered.connect(self._copy_messages)
        copy_html = menu.addAction("Copy as HTML")
        copy_html.triggered.connect(self._copy_html)
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
            if entry.pid:
                ex_pid = excl.addAction(f"PID: {entry.pid}")
                ex_pid.triggered.connect(
                    lambda _c=False, pid=entry.pid: self._add_query_token(f"-pid:{pid}")
                )
            if proc:
                ex_proc = excl.addAction(f"Package: {proc}")
                ex_proc.triggered.connect(
                    lambda _c=False, pr=proc: self._add_query_token(f"-proc:{pr}")
                )
            isolate = menu.addAction(
                "Show All" if self._isolate_prev_query is not None else "Isolate"
            )
            isolate.setEnabled(bool(entry.pid) or self._isolate_prev_query is not None)
            isolate.triggered.connect(lambda _c=False, e=entry: self._toggle_isolate(e))
            if entry.tag or entry.pid:
                goto = menu.addMenu("Go to same…")
                if entry.tag:
                    nt = goto.addAction(f"Next tag ‹{entry.tag}›")
                    nt.triggered.connect(
                        lambda _c=False, i=index: self._goto_same_from(i, "tag", 1)
                    )
                    pt = goto.addAction(f"Previous tag ‹{entry.tag}›")
                    pt.triggered.connect(
                        lambda _c=False, i=index: self._goto_same_from(i, "tag", -1)
                    )
                if entry.pid:
                    npid = goto.addAction(f"Next PID ‹{entry.pid}›")
                    npid.triggered.connect(
                        lambda _c=False, i=index: self._goto_same_from(i, "pid", 1)
                    )
                    ppid = goto.addAction(f"Previous PID ‹{entry.pid}›")
                    ppid.triggered.connect(
                        lambda _c=False, i=index: self._goto_same_from(i, "pid", -1)
                    )
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
        self._set_query_text((self.query.text() + " " + token).strip())
        self.table.viewport().update()
        self.statusBar().showMessage("Cleared tag highlights.")

    # --- save / load -------------------------------------------------------
    def _filtered_entries(self) -> list[LogEntry]:
        """The entries currently visible through the proxy (in order)."""
        return [
            self.model.entry_at(self.proxy.mapToSource(self.proxy.index(row, 0)).row())
            for row in range(self.proxy.rowCount())
        ]

    def _maybe_redact(self, entries: list[LogEntry]) -> list[LogEntry]:
        """Mask secrets when the Redact-on-Export toggle is on; else pass through.
        Non-destructive — redaction runs on a copy, never the master list."""
        return redact_entries(entries) if self.redact_action.isChecked() else entries

    def _write_log(self, entries: list[LogEntry], default_name: str) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Log", default_name, "Log files (*.log);;All files (*)"
        )
        if not path:
            return
        entries = self._maybe_redact(entries)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(entries_to_text(entries))
        except OSError as exc:
            self.statusBar().showMessage(f"Could not save: {exc}")
            return
        redacted = " (redacted)" if self.redact_action.isChecked() else ""
        self.statusBar().showMessage(f"Saved {len(entries)} lines to {Path(path).name}{redacted}.")
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
        entries = self._maybe_redact(self._filtered_entries())
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(formatter(entries))
        except OSError as exc:
            self.statusBar().showMessage(f"Could not export: {exc}")
            return
        redacted = " (redacted)" if self.redact_action.isChecked() else ""
        self.statusBar().showMessage(
            f"Exported {len(entries)} lines to {Path(path).name}{redacted}."
        )

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
            self.model.bookmarks(),
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
        self._set_query_text(data["query"])
        self.table.viewport().update()
        self.statusBar().showMessage(f"Loaded session from {Path(path).name}.")

    def _maybe_reopen_last(self) -> None:
        """On launch, reopen the most-recent log if the user opted in (and no live
        stream is running)."""
        if self.reopen_last_action.isChecked() and self._recent and self.reader is None:
            path = self._recent[0]
            self._load_log_file(path)  # launch: reuse the first tab, no new tab
            self._active.title = Path(path).name
            self._set_tab_label(self._active)

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
            self._open_log_in_tab(path)

    def _tab_is_reusable(self, sess) -> bool:
        """A tab is safe to load a file into only when it holds nothing worth
        keeping: no reader, no intent to stream, an empty model, and no
        loaded-file title. Anything else would blow away a recording or a log."""
        return (
            sess.reader is None
            and not sess.want_stream
            and sess.model.rowCount() == 0
            and not sess.title
        )

    def _open_log_in_tab(self, path: str) -> None:
        """Open a saved log in a new tab (reusing the current one when it's idle
        and empty), so existing recordings/logs in other tabs stay intact."""
        if not self._tab_is_reusable(self._active):
            self._new_tab()
        self._load_log_file(path)
        self._active.title = Path(path).name
        self._set_tab_label(self._active)

    _LARGE_FILE_BYTES = 5_000_000  # above this, load in the background with progress

    def _load_log_file(self, path: str) -> None:
        """Load a saved log into the offline view; used by Open and Open Recent.

        Large files stream in on a background thread with a cancelable progress
        dialog; small ones keep the instant synchronous path (no dialog flicker).
        """
        try:
            size = os.path.getsize(path)
        except OSError as exc:
            self.statusBar().showMessage(f"Could not open: {exc}")
            self._forget_recent(path)
            return
        # Opening is an offline view: stop any live stream and drop the
        # device-specific package (PID) filter, which no longer applies.
        if self.reader and self.reader.isRunning():
            self.stop()
        self.proxy.set_pids(None)
        self.model.clear()
        self.model.clear_process_names()  # offline: PIDs are from another capture

        if size > self._LARGE_FILE_BYTES:
            self._load_log_file_async(path)
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            self.statusBar().showMessage(f"Could not open: {exc}")
            self._forget_recent(path)
            return
        entries = text_to_entries(text)
        self.model.append_entries(entries)
        self.statusBar().showMessage(f"Loaded {len(entries)} lines from {Path(path).name}.")
        self._remember_recent(path)

    def _load_log_file_async(self, path: str) -> None:
        """Background path for big files: a FileLoader thread fills the model as it
        reads, behind a cancelable QProgressDialog."""
        if getattr(self, "_file_loader", None) is not None:
            self._file_loader.stop()  # only one loader at a time
            self._file_loader.wait(2000)
        dialog = QProgressDialog(f"Opening {Path(path).name}…", "Cancel", 0, 100, self)
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setMinimumDuration(0)
        loader = FileLoader(path, self)
        self._file_loader = loader

        def on_progress(read, total):
            dialog.setValue(int(read * 100 / total) if total else 0)

        def finish(message):
            dialog.reset()
            self._file_loader = None
            self.statusBar().showMessage(message)

        def on_done(n):
            finish(f"Loaded {n} lines from {Path(path).name}.")
            self._remember_recent(path)

        def on_error(msg):
            finish(f"Could not open: {msg}")
            self._forget_recent(path)

        loader.batch_ready.connect(self.model.append_entries)
        loader.progress.connect(on_progress)
        loader.done.connect(on_done)
        loader.error.connect(on_error)
        dialog.canceled.connect(loader.stop)
        loader.start()

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
            act.triggered.connect(lambda _checked=False, p=path: self._open_log_in_tab(p))
        self._recent_menu.addSeparator()
        self._recent_menu.addAction("Clear Recent").triggered.connect(self._clear_recent)

    # --- status counts -----------------------------------------------------
    def _schedule_counts(self, *args) -> None:
        self._counts_timer.start()  # coalesces a burst of row signals into one recompute

    def _do_follow_scroll(self) -> None:
        if not self.follow_check.isChecked():
            return
        if self.table.selectionModel().hasSelection():
            return  # selected between the batch arming this timer and it firing
        self.table.scrollToBottom()
        # In wrap mode the rows just scrolled into view are still one line tall until
        # fitted, so the first scrollToBottom stops short of the true bottom. Grow the
        # now-visible rows, then re-pin — otherwise Follow visibly lags behind.
        if self.log_delegate.wrap:
            self._fit_visible_rows()
            self.table.scrollToBottom()

    def _jump_to_latest(self) -> None:
        """Explicit "go to now" — let go of any selection so Follow's
        auto-scroll gate (`not hasSelection()`) resumes tailing on the next batch."""
        self.table.clearSelection()
        self.table.scrollToBottom()

    def _arm_scroll_clear_suppression(self, *_args) -> None:
        self._suppress_next_scroll_clear = True
        # Selecting a row that's already fully visible triggers no scroll at
        # all, so there'd be nothing to consume this flag — self-disarm on
        # the next event-loop turn so it can't linger and wrongly swallow a
        # later, genuinely independent user scroll.
        QTimer.singleShot(0, self._disarm_scroll_clear_suppression)

    def _disarm_scroll_clear_suppression(self) -> None:
        self._suppress_next_scroll_clear = False

    def _maybe_resume_follow_on_scroll(self, value: int) -> None:
        """If the user scrolls all the way back to the newest line themselves
        (not as a side effect of selecting a row, which auto-scrolls the row
        into view), let go of any stale selection so Follow's auto-scroll gate
        can resume tailing on the next batch — otherwise a selection made
        while reading history would block Follow forever, even after
        returning to the tail."""
        if self._suppress_next_scroll_clear:
            self._suppress_next_scroll_clear = False
            return
        sb = self.table.verticalScrollBar()
        if value >= sb.maximum() - 4 and self.table.selectionModel().hasSelection():
            self.table.clearSelection()

    def _update_counts(self, *args) -> None:
        total = self.model.rowCount()
        visible = self.proxy.rowCount()
        # Once a filter is hiding rows, tally the levels of what's actually shown
        # instead of the whole buffer — otherwise "Showing X of Y" reads as if the
        # per-level counts describe X when they'd still describe Y.
        counts = self.proxy.level_counts() if visible < total else self.model.level_counts()
        self.count_label.setText(format_level_summary(total, counts, visible))
        self.incident_label.setText(format_incident_summary(self.model.incident_counts()))
        start = max(0, total - 500)
        ranks = [self.model.entry_at(r).rank for r in range(start, total)]
        self.spark_label.setText(error_rate_sparkline(ranks, LEVEL_RANK["E"]))

    # --- detail pane -------------------------------------------------------
    def _edit_extractors(self) -> None:
        """Edit the regex field-extractors (one pattern per line, named groups)."""
        text, ok = QInputDialog.getMultiLineText(
            self,
            "Extract fields",
            "One regex per line, using named groups, e.g.\n"
            "latency=(?P<ms>\\d+)ms\n\nExtracted fields show in the detail pane.",
            "\n".join(self._extract_patterns),
        )
        if not ok:
            return
        self._extract_patterns = [ln.strip() for ln in text.splitlines() if ln.strip()]
        self.model.set_extractors(self._extract_patterns)
        self._update_detail(self.table.currentIndex())  # refresh the shown fields
        self._save_settings()

    def _update_detail(self, current, previous=None) -> None:
        if current is None or not current.isValid():
            self.detail.clear()
            return
        src = self.proxy.mapToSource(current).row()
        entry = self.model.entry_at(src)
        dash = "\u2014"
        header = (
            f"Time  {entry.time or dash}    "
            f"PID {entry.pid or dash}  TID {entry.tid or dash}    "
            f"{entry.level or dash}  {entry.tag or dash}"
        )
        if entry.source:  # merged multi-device view
            header += f"    device {entry.source}"
        text = header + "\n\n" + entry.message
        fields = self.model.extract_fields(src)
        if fields:
            text += "\n\nExtracted fields:\n" + "\n".join(f"  {k} = {v}" for k, v in fields.items())
        self.detail.setPlainText(text)

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

        def set_highlight_rules(v):
            self.model.set_highlight_rules(normalize_rules(v))

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

        def set_recent(v):
            self._recent = normalize_history(v, limit=10)
            self._rebuild_recent_menu()

        def set_watch(v):
            self._apply_watch(v if isinstance(v, str) else "", announce=False)

        def set_extract_patterns(v):
            items = v if isinstance(v, list) else []
            self._extract_patterns = [str(p) for p in items if str(p).strip()]
            self.model.set_extractors(self._extract_patterns)

        def set_collapse(v):
            self.collapse_action.setChecked(bool(v))
            self.proxy.set_collapse(bool(v))
            self.log_delegate.collapse = bool(v)

        def set_fold(v):
            # setChecked fires _on_fold_toggled, which folds/unfolds + invalidates.
            self.fold_action.setChecked(bool(v))

        def set_font_delta(v):
            delta = v if isinstance(v, int) else 0
            self._font_delta = max(-4, min(12, delta))
            self._apply_font()

        def set_font_family(v):
            self._set_font_family(str(v) if v else "")

        def set_density(v):
            self._set_density(v if v in DENSITY_NAMES else DEFAULT_DENSITY)

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

        def set_line_numbers(v):
            self.log_delegate.line_numbers = bool(v)
            self._apply_row_height()  # the gutter narrows the message -> re-fit wrap heights
            self.table.viewport().update()

        def set_adb_path(v):
            self._adb_path_setting = str(v) if v else ""

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
            ("highlight_rules", self.model.highlight_rules, set_highlight_rules),
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
            ("font_family", lambda: self._font_family, set_font_family),
            ("density", lambda: self._density, set_density),
            ("search_history", lambda: self._history, set_search_history),
            ("recent_files", lambda: self._recent, set_recent),
            ("watch", lambda: self._watch_pattern, set_watch),
            ("extract_patterns", lambda: self._extract_patterns, set_extract_patterns),
            ("collapse", self.collapse_action.isChecked, set_collapse),
            ("fold_traces", self.fold_action.isChecked, set_fold),
            (
                "show_histogram",
                self.histogram_action.isChecked,
                lambda v: self.histogram_action.setChecked(bool(v)),
            ),
            (
                "show_sticky_header",
                self.sticky_action.isChecked,
                lambda v: self.sticky_action.setChecked(bool(v)),
            ),
            (
                "redact_on_export",
                self.redact_action.isChecked,
                lambda v: self.redact_action.setChecked(bool(v)),
            ),
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
            ("line_numbers", lambda: self.log_delegate.line_numbers, set_line_numbers),
            ("adb_path", lambda: self._adb_path_setting, set_adb_path),
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
            _log.exception("Failed to save settings")  # never break shutdown over it

    # --- actions -----------------------------------------------------------
    def start(self) -> None:
        if self.reader and self.reader.isRunning():
            return
        # A local pseudo-source ("This PC") shares the picker and this button but
        # is captured by its own reader — never handed to adb.
        if is_local_source(self.device_box.currentData()):
            self.capture_debug_output()
            return
        if self.clear_on_start_action.isChecked():
            self.model.clear()
        self._want_stream = True
        self._last_time = ""
        self._reconnect_serial = self.device_box.currentData()
        _log.info("Start requested (device=%r)", self._reconnect_serial or "default")
        self._start_reader(self._reconnect_serial)
        if self.process_action.isChecked():
            self._refresh_process_map()

    def _start_reader(self, serial, since_time=None, sess=None) -> None:
        sess = sess if sess is not None else self._active
        buffers = [name for name, act in self._buffer_actions.items() if act.isChecked()]
        tail = next((c for c, a in self._tail_actions.items() if a.isChecked()), 0)
        reader = AdbReader(
            serial=serial,
            adb_path=self._adb_path(),
            buffers=buffers or None,
            tail=tail,
            since_time=since_time,
        )
        # A device stream labels by serial, so no stream_label.
        self.capture.attach(sess, reader, serial=serial or "", track_end=True)
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

    def start_merged(self) -> None:
        """Stream every connected device into one view, tagging lines by serial
        (merged multi-device view). Filter with `device:<serial>`."""
        if (self.reader and self.reader.isRunning()) or self.capture.streaming:
            return
        # Real, online devices only: "This PC" isn't an adb device, and
        # `d.streamable` is the per-device check (is_serial_streamable answers a
        # different question — whether a *named* serial is back — and needs the list).
        serials = [d.serial for d in self.devctl.devices if d.streamable and not d.is_local]
        if len(serials) < 2:
            self.statusBar().showMessage("Merged view needs at least two connected devices.")
            return
        if self.clear_on_start_action.isChecked():
            self.model.clear()
        self.model.clear_process_names()  # PIDs from several devices — don't cross-wire names
        buffers = [name for name, act in self._buffer_actions.items() if act.isChecked()]
        tail = next((c for c, a in self._tail_actions.items() if a.isChecked()), 0)
        sess = self._active
        for serial in serials:
            reader = AdbReader(
                serial=serial,
                adb_path=self._adb_path(),
                buffers=buffers or None,
                tail=tail,
                source=serial,
            )
            self.capture.attach(sess, reader, primary=False)
        self.device_box.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        _log.info("Merged streaming %d devices: %s", len(serials), ", ".join(serials))
        self.statusBar().showMessage(f"Merged streaming {len(serials)} devices…")

    def capture_debug_output(self) -> None:
        """Capture the OutputDebugString stream of Windows apps into a tab
        (DebugView-style). Focus on your target with `proc:` / `pid:`. Opens a
        fresh tab when the current one is busy, so existing logs/streams stay put."""
        from zlog.winlog.dbwin_reader import DebugOutputReader, is_supported

        if not is_supported():
            self.statusBar().showMessage("Capturing debug output is only available on Windows.")
            return
        if not self._tab_is_reusable(self._active):
            self._new_tab()
        sess = self._active
        if sess.reader and sess.reader.isRunning():
            return
        if self.clear_on_start_action.isChecked():
            self.model.clear()
        self.capture.attach(sess, DebugOutputReader(), stream_label="Debug Output")
        self._set_tab_label(sess)
        self._set_streaming_controls()  # Stop/pause on, Start off (as _start_reader does)
        _log.info("DBWIN capture requested")
        self.statusBar().showMessage("Capturing Windows debug output (OutputDebugString)…")

    def focus_app(self) -> None:
        """Pick a running process and narrow the view to it — the Windows
        counterpart of the Android package filter. Focus is expressed as a
        `proc:`/`pid:` query token, so chips, presets, and export all follow."""
        from zlog.core.procinfo import focus_query
        from zlog.ui.process_dialog import ProcessPickerDialog

        dialog = ProcessPickerDialog(parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        proc = dialog.selected()
        if proc is None:
            return
        if dialog.focus_by_pid():
            text = focus_query(self.query.text(), pid=proc.pid)
        else:
            text = focus_query(self.query.text(), name=proc.name)
        self._set_query_text(text)
        self.statusBar().showMessage(f"Focused on {proc.label}.")

    def launch_app(self) -> None:
        """Start a program and capture it from its first line: its console output
        via LaunchReader, plus (on Windows) its OutputDebugString via the DBWIN
        reader. Both feed the same tab; Stop stops both."""
        from zlog.core.procinfo import focus_query
        from zlog.ui.launch_dialog import LaunchDialog
        from zlog.winlog.launcher import LaunchReader, build_argv

        exe, arguments, cwd = "", "", ""
        if self._last_launch:
            exe, arguments, cwd = self._last_launch
        dialog = LaunchDialog(exe, arguments, cwd, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        exe, arguments, cwd = dialog.get_values()
        if not exe:
            return
        self._last_launch = (exe, arguments, cwd)

        if not self._tab_is_reusable(self._active):
            self._new_tab()
        sess = self._active
        if self.clear_on_start_action.isChecked():
            self.model.clear()
        reader = LaunchReader(build_argv(exe, arguments), cwd or None)
        self.capture.attach(
            sess,
            reader,
            stream_label=reader.app_name or "App",
            on_end=self._on_launched_app_exited,
        )
        self._set_tab_label(sess)
        # On Windows the app's OutputDebugString tracing is a separate channel;
        # capture it alongside so "launch and watch" catches both. Attached as an
        # extra, so the shared detach() tears it down too.
        self._start_dbwin_alongside()
        # Focus on the launched app by name (survives it restarting itself).
        if reader.app_name:
            self._set_query_text(focus_query(self.query.text(), name=reader.app_name))
        self._set_streaming_controls()
        _log.info("Launched app capture: %r", exe)
        self.statusBar().showMessage(f"Launched {reader.app_name} — capturing output…")

    def _start_dbwin_alongside(self) -> None:
        """Add a DBWIN capture to the active tab (Windows only, best-effort): a
        launched app's debug output is a different channel from its console."""
        from zlog.winlog.dbwin_reader import DebugOutputReader, is_supported

        if not is_supported():
            return
        # A contended DBWIN buffer must not kill the console capture, so its errors
        # only reach the status bar rather than on_error (which stops everything).
        self.capture.attach(
            self._active,
            DebugOutputReader(),
            primary=False,
            on_error=self.statusBar().showMessage,
        )

    def _on_launched_app_exited(self, sess) -> None:
        """The launched app closed by itself — keep its output on screen and just
        report it (unlike a device drop, there's nothing to reconnect to)."""
        if sess is self._active:
            self.statusBar().showMessage("The launched app exited.")

    def _set_streaming_controls(self) -> None:
        """Toolbar state while the active tab streams (shared by the capture paths)."""
        self.device_box.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.pause_btn.setEnabled(True)
        self.pause_btn.setText("Pause")

    def stop(self) -> None:
        sess = self._active
        sess.want_stream = False
        sess.reconnect_timer.stop()
        self.capture.detach(sess)  # primary reader + any extras, in one place
        self.refresh_btn.setEnabled(True)
        self.device_box.setEnabled(bool(self.devctl.devices))
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("Pause")
        self._update_start_enabled()
        self._set_tab_label(sess)
        _log.info("Stopped stream (device=%r)", sess.serial or "default")
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
            # Selecting a row (a click, or F3/Ctrl+G/bookmark-next) doesn't move the
            # scrollbar, so without this check a batch right after selecting an
            # older row would still see "at the bottom" and yank the view away from
            # what the user just selected — treat an active selection like being
            # scrolled away from the bottom.
            at_bottom = sb.value() >= sb.maximum() - 4
            was_at_bottom = at_bottom and not self.table.selectionModel().hasSelection()
        sess.model.append_entries(entries)
        if active:
            if self.follow_check.isChecked() and was_at_bottom:
                self._scroll_timer.start()  # coalesced follow scroll
            else:
                self._scroll_timer.stop()  # user scrolled up (or off): cancel pending scroll

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
            devices = list_devices(self._adb_path())
        except Exception:
            return  # adb hiccup; keep polling
        if is_serial_streamable(devices, sess.reconnect_serial):
            sess.reconnect_timer.stop()
            if sess is self._active:
                self.statusBar().showMessage("Device back — reconnecting…")
            self._start_reader(sess.reconnect_serial, since_time=sess.last_time or None, sess=sess)

    def on_error(self, msg: str) -> None:
        self.statusBar().showMessage(msg)
        self.stop()

    def closeEvent(self, event) -> None:
        self._save_settings()
        self.stop()
