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

from PySide6.QtCore import QByteArray, QStandardPaths, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
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
from zlog.adb.packages import list_packages, resolve_pids
from zlog.adb.reader import AdbReader
from zlog.core.devices import Device
from zlog.core.models import LogEntry
from zlog.core.presets import make_preset, normalize_presets, remove_preset, upsert_preset
from zlog.core.search import compile_matcher
from zlog.core.session import entries_to_text, text_to_entries
from zlog.core.settings import DEFAULTS, load_settings, save_settings
from zlog.core.summary import format_level_summary
from zlog.ui.device_controller import DeviceController
from zlog.ui.log_model import COLUMNS, MESSAGE_COL, LogFilterProxy, LogTableModel
from zlog.ui.table_view import LogTableView
from zlog.ui.theme import THEMES, build_stylesheet

LEVELS = ["V", "D", "I", "W", "E", "F"]


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

        # Row 1: device + stream controls.
        self.device_box = QComboBox()
        self.device_box.setMinimumWidth(180)
        self.refresh_btn = QPushButton("Refresh")
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.clear_btn = QPushButton("Clear")
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
            self.level_box.addItem(letter, letter)

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

    def _build_layout(self) -> None:
        """Arrange the widgets built in _build_widgets into the window."""
        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.addWidget(self.table)
        self._splitter.addWidget(self.detail)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([520, 150])

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Device:"))
        row1.addWidget(self.device_box)
        row1.addWidget(self.refresh_btn)
        row1.addSpacing(16)
        row1.addWidget(self.start_btn)
        row1.addWidget(self.stop_btn)
        row1.addWidget(self.clear_btn)
        row1.addWidget(self.follow_check)
        row1.addWidget(self.to_top_btn)
        row1.addWidget(self.to_latest_btn)
        row1.addStretch(1)

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
        row2.addWidget(self.match_prev_btn)
        row2.addWidget(self.match_label)
        row2.addWidget(self.match_next_btn)
        row2.addWidget(self.exclude)
        row2.addWidget(self.regex_check)
        row2.addWidget(self.case_check)
        row2.addWidget(self.search_mode_box)
        row2.addWidget(self.clear_filters_btn)

        layout = QVBoxLayout()
        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addWidget(self._splitter)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.setStatusBar(QStatusBar())
        self.statusBar().addPermanentWidget(self.count_label)

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

        clear_filters_act = view_menu.addAction("Clear F&ilters")
        clear_filters_act.triggered.connect(self.clear_filters)

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
        self.load_pkgs_btn.clicked.connect(self.load_packages)
        self.apply_pkg_btn.clicked.connect(self.apply_package_filter)
        self.clear_pkg_btn.clicked.connect(self.clear_package_filter)
        self.package_box.lineEdit().returnPressed.connect(self.apply_package_filter)
        self.level_box.currentIndexChanged.connect(
            lambda: self.proxy.set_min_level(self.level_box.currentData())
        )
        self.search.textChanged.connect(self._apply_search)
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
        self.level_box.setCurrentIndex(0)  # V — fires the min-level update
        self.regex_check.setChecked(False)
        self.case_check.setChecked(False)
        self.search.clear()  # fires _apply_search, which clears the error tint
        self.exclude.clear()
        self.clear_package_filter()
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
        idx = self.level_box.findData(preset.get("min_level", "V"))
        if idx >= 0:
            self.level_box.setCurrentIndex(idx)
        self.regex_check.setChecked(bool(preset.get("regex")))
        self.case_check.setChecked(bool(preset.get("case")))
        self.search.setText(preset.get("search", ""))
        package = preset.get("package", "")
        self.package_box.setEditText(package)
        if package:
            self.apply_package_filter()  # resolves PIDs when a device is available
        else:
            self.clear_package_filter()
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
        exclude_ok = self.proxy.set_exclude(self.exclude.text(), regex, case)
        if exclude_ok:
            self.exclude.setStyleSheet("")
        else:
            self.exclude.setStyleSheet(
                f"QLineEdit {{ background-color: {self._search_error_color}; }}"
            )
            self.statusBar().showMessage("Invalid exclude regex — keeping the previous one.")
        self._update_match_label()

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

    # --- theme -------------------------------------------------------------
    def apply_theme(self, name: str) -> None:
        self._theme_name = name
        theme = THEMES[name]
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet(theme))
        self.model.set_level_colors(theme.level_colors)
        self.model.set_highlight_color(theme.search_highlight)
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
            if not isinstance(v, list):
                return
            for col, act in enumerate(self._column_actions):
                visible = col not in v
                act.setChecked(visible)
                self.table.setColumnHidden(col, not visible)

        def set_tag_highlights(v):
            if isinstance(v, dict):
                for tag, color in v.items():
                    self.model.set_tag_color(str(tag), str(color))

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
            (
                "hidden_columns",
                lambda: [
                    c for c in range(len(self._column_actions)) if self.table.isColumnHidden(c)
                ],
                set_hidden_columns,
            ),
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
        self.device_box.setEnabled(bool(self.devctl.devices))
        self.stop_btn.setEnabled(False)
        self._update_start_enabled()
        self.statusBar().showMessage("Stopped.")

    def on_batch(self, entries) -> None:
        self.model.append_entries(entries)
        if self.devctl.filtering:
            self._track_new_pids(entries)
        if self.follow_check.isChecked():
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
        super().closeEvent(event)
