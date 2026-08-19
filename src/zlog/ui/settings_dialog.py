"""A tabbed Settings/Preferences dialog.

Pure Qt view: it takes the current values plus the option lists and returns the
chosen values via ``get_values()``. The MainWindow owns *applying* and persisting
them (by driving its existing actions/widgets), so this dialog stays decoupled and
unit-testable without a running window.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# core.adbpath.resolve_adb's `source` values, in human terms.
_ADB_SOURCE_LABELS = {
    "setting": "Settings override",
    "path": "found on PATH",
    "managed": "downloaded by zLog",
    "none": "not found",
}


class SettingsDialog(QDialog):
    def __init__(
        self,
        values,
        *,
        themes,
        time_modes,
        tail_options,
        buffers,
        fonts=(),
        on_edit_theme=None,
        adb_effective=None,  # (path, source) from core.adbpath.resolve_adb, for display only
        on_download_adb=None,
        managed_adb_path=None,  # path of a copy zLog already downloaded, if any (see bundle-adb.md)
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        tabs = QTabWidget()

        # --- Appearance ---------------------------------------------------
        self.theme_box = QComboBox()
        for name in themes:
            self.theme_box.addItem(name, name)
        self._select(self.theme_box, values.get("theme", "Light"))
        theme_row = QHBoxLayout()
        theme_row.addWidget(self.theme_box)
        if on_edit_theme is not None:
            edit_theme_btn = QPushButton("Edit theme…")
            edit_theme_btn.clicked.connect(on_edit_theme)
            theme_row.addWidget(edit_theme_btn)
        self.font_box = QComboBox()
        self.font_box.addItem("Default (built-in monospace)", "")
        for family in fonts:
            self.font_box.addItem(family, family)
        self._select(self.font_box, values.get("font_family", ""))
        self.font_spin = QSpinBox()
        self.font_spin.setRange(-4, 12)
        self.font_spin.setValue(int(values.get("font_delta", 0)))
        self.font_spin.setSuffix(" pt")
        self.details_chk = QCheckBox("Show the detail pane")
        self.details_chk.setChecked(values.get("show_details", True))
        appearance = QFormLayout()
        appearance.addRow("Theme", theme_row)
        appearance.addRow("Log font", self.font_box)
        appearance.addRow("Font size offset", self.font_spin)
        appearance.addRow(self.details_chk)
        tabs.addTab(self._wrap(appearance), "Appearance")

        # --- Log view -----------------------------------------------------
        self.time_box = QComboBox()
        for label, data in time_modes:
            self.time_box.addItem(label, data)
        self._select(self.time_box, values.get("time_mode", "absolute"))
        self.density_box = QComboBox()
        for label, data in (
            ("Compact", "compact"),
            ("Default", "default"),
            ("Comfortable", "comfortable"),
        ):
            self.density_box.addItem(label, data)
        self._select(self.density_box, values.get("density", "default"))
        self.highlight_chk = QCheckBox("Highlight matches instead of hiding non-matches")
        self.highlight_chk.setChecked(values.get("highlight", False))
        self.case_chk = QCheckBox("Case-sensitive search")
        self.case_chk.setChecked(values.get("case", False))
        self.collapse_chk = QCheckBox("Collapse repeated lines")
        self.collapse_chk.setChecked(values.get("collapse", False))
        self.process_chk = QCheckBox("Show process / package names")
        self.process_chk.setChecked(values.get("show_process", False))
        self.wrap_chk = QCheckBox("Wrap long messages (show the full message)")
        self.wrap_chk.setChecked(values.get("wrap", False))
        self.linenum_chk = QCheckBox("Show line numbers (source-row gutter)")
        self.linenum_chk.setChecked(values.get("line_numbers", False))
        logview = QFormLayout()
        logview.addRow("Time display", self.time_box)
        logview.addRow("Row density", self.density_box)
        logview.addRow(self.highlight_chk)
        logview.addRow(self.case_chk)
        logview.addRow(self.collapse_chk)
        logview.addRow(self.process_chk)
        logview.addRow(self.wrap_chk)
        logview.addRow(self.linenum_chk)
        tabs.addTab(self._wrap(logview), "Log view")

        # --- Capture ------------------------------------------------------
        self.buffer_chks: dict[str, QCheckBox] = {}
        buf_box = QGroupBox("adb log buffers (applied on next Start)")
        buf_layout = QVBoxLayout(buf_box)
        selected = set(values.get("buffers", []))
        for name in buffers:
            chk = QCheckBox(name)
            chk.setChecked(name in selected)
            self.buffer_chks[name] = chk
            buf_layout.addWidget(chk)
        self.tail_box = QComboBox()
        for label, data in tail_options:
            self.tail_box.addItem(label, data)
        self._select(self.tail_box, values.get("tail", 0))
        self.max_spin = QSpinBox()
        self.max_spin.setRange(0, 100_000_000)
        self.max_spin.setSingleStep(1000)
        self.max_spin.setGroupSeparatorShown(True)
        self.max_spin.setSpecialValueText("Unlimited")  # shown when value == 0
        self.max_spin.setValue(int(values.get("max_rows", 0)))
        self.clear_start_chk = QCheckBox("Clear the view when starting a new stream")
        self.clear_start_chk.setChecked(values.get("clear_on_start", False))
        self.adb_path_edit = QLineEdit(values.get("adb_path", ""))
        self.adb_path_edit.setPlaceholderText("adb (from PATH)")
        adb_browse = QPushButton("Browse…")
        adb_browse.clicked.connect(self._browse_adb_path)
        adb_path_row = QHBoxLayout()
        adb_path_row.addWidget(self.adb_path_edit)
        adb_path_row.addWidget(adb_browse)
        if managed_adb_path is not None:
            use_managed_btn = QPushButton("Use downloaded copy")
            use_managed_btn.setToolTip(managed_adb_path)
            use_managed_btn.clicked.connect(lambda: self.adb_path_edit.setText(managed_adb_path))
            adb_path_row.addWidget(use_managed_btn)
        if on_download_adb is not None:
            download_btn = QPushButton("Download adb…")
            download_btn.clicked.connect(on_download_adb)
            adb_path_row.addWidget(download_btn)
        self.addr2line_path_edit = QLineEdit(values.get("addr2line_path", ""))
        self.addr2line_path_edit.setPlaceholderText("addr2line (from PATH)")
        addr2line_browse = QPushButton("Browse…")
        addr2line_browse.clicked.connect(self._browse_addr2line_path)
        addr2line_path_row = QHBoxLayout()
        addr2line_path_row.addWidget(self.addr2line_path_edit)
        addr2line_path_row.addWidget(addr2line_browse)

        capture = QFormLayout()
        capture.addRow(buf_box)
        capture.addRow("Start from", self.tail_box)
        capture.addRow("Buffer limit (lines)", self.max_spin)
        capture.addRow(self.clear_start_chk)
        capture.addRow("adb path", adb_path_row)
        capture.addRow("addr2line path", addr2line_path_row)
        if adb_effective is not None:
            path, source = adb_effective
            # word-wrap: a real adb path (e.g. the nested AppData\Local\Android\Sdk\
            # ...\adb.EXE Android Studio installs to) routinely overflows the field
            # column width — without it Qt clips the text at the widget boundary
            # instead of reflowing it.
            effective_label = QLabel(f"{path}  ({_ADB_SOURCE_LABELS[source]})")
            effective_label.setWordWrap(True)
            effective_label.setToolTip(path)
            capture.addRow("Currently using", effective_label)
        tabs.addTab(self._wrap(capture), "Capture")

        # --- Behavior -----------------------------------------------------
        self.follow_chk = QCheckBox("Follow the tail (auto-scroll to newest)")
        self.follow_chk.setChecked(values.get("follow", True))
        self.reopen_chk = QCheckBox("Reopen the last log on launch")
        self.reopen_chk.setChecked(values.get("reopen_last", False))
        self.autosave_chk = QCheckBox("Autosave capture to disk while streaming")
        self.autosave_chk.setChecked(values.get("autosave", False))
        behavior = QFormLayout()
        behavior.addRow(self.follow_chk)
        behavior.addRow(self.reopen_chk)
        behavior.addRow(self.autosave_chk)
        tabs.addTab(self._wrap(behavior), "Behavior")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(tabs)
        root.addWidget(buttons)

    @staticmethod
    def _wrap(layout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    @staticmethod
    def _select(box: QComboBox, data) -> None:
        i = box.findData(data)
        if i >= 0:
            box.setCurrentIndex(i)

    def set_themes(self, themes, current: str) -> None:
        """Repopulate the theme dropdown — called after the theme editor saves
        a new custom theme, so it's selectable without closing and reopening
        Settings."""
        self.theme_box.clear()
        for name in themes:
            self.theme_box.addItem(name, name)
        self._select(self.theme_box, current)

    def _browse_adb_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Locate adb executable")
        if path:
            self.adb_path_edit.setText(path)

    def _browse_addr2line_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Locate addr2line/llvm-addr2line executable")
        if path:
            self.addr2line_path_edit.setText(path)

    def get_values(self) -> dict:
        return {
            "theme": self.theme_box.currentData(),
            "font_family": self.font_box.currentData(),
            "font_delta": self.font_spin.value(),
            "show_details": self.details_chk.isChecked(),
            "time_mode": self.time_box.currentData(),
            "density": self.density_box.currentData(),
            "highlight": self.highlight_chk.isChecked(),
            "case": self.case_chk.isChecked(),
            "collapse": self.collapse_chk.isChecked(),
            "show_process": self.process_chk.isChecked(),
            "wrap": self.wrap_chk.isChecked(),
            "line_numbers": self.linenum_chk.isChecked(),
            "buffers": {n for n, c in self.buffer_chks.items() if c.isChecked()},
            "tail": self.tail_box.currentData(),
            "max_rows": self.max_spin.value(),
            "clear_on_start": self.clear_start_chk.isChecked(),
            "adb_path": self.adb_path_edit.text().strip(),
            "addr2line_path": self.addr2line_path_edit.text().strip(),
            "follow": self.follow_chk.isChecked(),
            "reopen_last": self.reopen_chk.isChecked(),
            "autosave": self.autosave_chk.isChecked(),
        }
