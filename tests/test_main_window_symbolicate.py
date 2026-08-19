"""End-to-end MainWindow tests for crash symbolication: loading a mapping
file actually changes what's shown, the toggle actually toggles, export/copy
match the view, settings round-trip, and the native-frame resolution pipeline
wires together. See docs/plans/crash-symbolication.md.
"""

from __future__ import annotations

import pytest

_MAPPING_TEXT = "com.example.app.MainActivity -> com.example.app.a:\n    void run() -> a\n"


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    path = tmp_path / "settings.json"
    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: path)
    return MainWindow()


def _seed_obfuscated_line(window):
    from zlog.core.models import LogEntry

    entry = LogEntry(
        time="06-30 12:00:00.000",
        pid="1",
        tid="2",
        level="E",
        tag="AndroidRuntime",
        message="    at com.example.app.a.a(SourceFile:1)",
    )
    window.model.append_entries([entry])
    window.table.selectRow(0)
    return entry


def test_loading_a_mapping_file_updates_the_detail_pane(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    _seed_obfuscated_line(window)
    mapping_path = tmp_path / "mapping.txt"
    mapping_path.write_text(_MAPPING_TEXT, encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(mapping_path), ""))
    window._load_mapping_file()
    window._update_detail(window.table.currentIndex())
    assert "MainActivity" in window.detail.toPlainText()
    assert "com.example.app.a.a" not in window.detail.toPlainText()


def test_toggle_off_shows_raw_without_discarding_the_mapping(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    _seed_obfuscated_line(window)
    mapping_path = tmp_path / "mapping.txt"
    mapping_path.write_text(_MAPPING_TEXT, encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(mapping_path), ""))
    window._load_mapping_file()

    window.symbolicate_check.setChecked(False)
    window._update_detail(window.table.currentIndex())
    assert "com.example.app.a.a" in window.detail.toPlainText()

    window.symbolicate_check.setChecked(True)
    window._update_detail(window.table.currentIndex())
    assert "MainActivity" in window.detail.toPlainText()


def test_clear_mapping_reverts_to_raw(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    _seed_obfuscated_line(window)
    mapping_path = tmp_path / "mapping.txt"
    mapping_path.write_text(_MAPPING_TEXT, encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(mapping_path), ""))
    window._load_mapping_file()
    window._clear_mapping_file()
    window._update_detail(window.table.currentIndex())
    assert "com.example.app.a.a" in window.detail.toPlainText()
    assert window.mapping_path_edit.text() == ""


def test_selected_text_reflects_the_symbolicated_message(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    _seed_obfuscated_line(window)
    mapping_path = tmp_path / "mapping.txt"
    mapping_path.write_text(_MAPPING_TEXT, encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(mapping_path), ""))
    window._load_mapping_file()
    window.table.selectAll()
    text = window._selected_text()
    assert "MainActivity" in text


def test_save_log_writes_symbolicated_text(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    _seed_obfuscated_line(window)
    mapping_path = tmp_path / "mapping.txt"
    mapping_path.write_text(_MAPPING_TEXT, encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(mapping_path), ""))
    window._load_mapping_file()

    out = tmp_path / "out.log"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))
    window.save_log()
    assert "MainActivity" in out.read_text(encoding="utf-8")


def test_settings_round_trip_reloads_and_reparses_the_mapping(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from zlog.ui.main_window import MainWindow

    _seed_obfuscated_line(window)
    mapping_path = tmp_path / "mapping.txt"
    mapping_path.write_text(_MAPPING_TEXT, encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(mapping_path), ""))
    window._load_mapping_file()
    window.symbolicate_check.setChecked(False)
    window._toggle_symbolicate(False)
    window._save_settings()

    w2 = MainWindow()
    assert w2._mapping_path == str(mapping_path)
    assert w2._symbolicator.mapping is not None
    assert w2._symbolicator.mapping.deobfuscate_class("com.example.app.a") == (
        "com.example.app.MainActivity"
    )
    assert w2._symbolicator.enabled is False
    assert w2.symbolicate_check.isChecked() is False


def test_deleted_mapping_path_is_dropped_quietly_on_reload(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from zlog.ui.main_window import MainWindow

    mapping_path = tmp_path / "mapping.txt"
    mapping_path.write_text(_MAPPING_TEXT, encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(mapping_path), ""))
    window._load_mapping_file()
    window._save_settings()
    mapping_path.unlink()

    w2 = MainWindow()  # must not raise
    assert w2._symbolicator.mapping is None
    assert w2._mapping_path == ""


def test_native_symbols_dir_round_trips(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from zlog.ui.main_window import MainWindow

    symbols_dir = tmp_path / "symbols"
    symbols_dir.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: str(symbols_dir))
    window._load_native_symbols_dir()
    window._save_settings()

    w2 = MainWindow()
    assert w2._symbols_dir == str(symbols_dir)
    assert w2.symbols_dir_edit.toolTip() == str(symbols_dir)


def test_native_frame_resolution_pipeline_updates_the_cache_and_view(window, tmp_path, monkeypatch):
    """End-to-end: a batch containing a native frame triggers resolution, and
    the result lands in the Symbolicator's cache and the detail pane, without
    ever touching a real addr2line/toolchain."""
    from zlog.core.models import LogEntry
    from zlog.ui import main_window as mw

    symbols_dir = tmp_path / "symbols"
    symbols_dir.mkdir()
    (symbols_dir / "libnative.so").write_bytes(b"")
    window._symbols_dir = str(symbols_dir)

    class FakeResolver:
        def __init__(self, pairs, symbols_dir, addr2line_exe, device_abi, parent=None):
            self.pairs = pairs
            self.resolved = _FakeSignal()

        def start(self):
            result = {pair: "crash_handler+16" for pair in self.pairs}
            self.resolved._fire(result)

    class _FakeSignal:
        def __init__(self):
            self._slots = []

        def connect(self, slot):
            self._slots.append(slot)

        def _fire(self, value):
            for slot in self._slots:
                slot(value)

    monkeypatch.setattr(mw, "NativeSymbolResolver", FakeResolver)

    entry = LogEntry(
        time="",
        pid="100",
        tid="100",
        level="F",
        tag="DEBUG",
        message="    #00 pc 00001000  /system/lib64/libnative.so (offset 0x1000)",
    )
    window.model.append_entries([entry])
    window._maybe_resolve_native_frames([entry])

    assert window._symbolicator.native_cache[("libnative.so", "00001000")] == "crash_handler+16"
    window.table.selectRow(0)
    window._update_detail(window.table.currentIndex())
    assert "crash_handler+16" in window.detail.toPlainText()


def test_native_frame_never_resubmitted_while_already_pending(window, tmp_path, monkeypatch):
    from zlog.core.models import LogEntry
    from zlog.ui import main_window as mw

    symbols_dir = tmp_path / "symbols"
    symbols_dir.mkdir()
    window._symbols_dir = str(symbols_dir)

    calls = []

    class FakeResolver:
        def __init__(self, pairs, symbols_dir, addr2line_exe, device_abi, parent=None):
            calls.append(pairs)
            self.resolved = _NullSignal()

        def start(self):
            pass  # never completes -- simulates an in-flight resolution

    class _NullSignal:
        def connect(self, slot):
            pass

    monkeypatch.setattr(mw, "NativeSymbolResolver", FakeResolver)

    entry = LogEntry(
        time="",
        pid="100",
        tid="100",
        level="F",
        tag="DEBUG",
        message="    #00 pc 00001000  /system/lib64/libnative.so (offset 0x1000)",
    )
    window._maybe_resolve_native_frames([entry])
    window._maybe_resolve_native_frames([entry])  # same frame again, still "in flight"
    assert len(calls) == 1
