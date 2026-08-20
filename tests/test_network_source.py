"""NetworkDialog and its window wiring (offscreen Qt). `NetworkReader` itself
is exercised end-to-end in tests/test_net_reader.py; this file covers the
dialog's own validation and how `listen_network()` wires a real reader into a
tab (using a real ephemeral-port listener — no external network needed).
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QDialog, QDialogButtonBox


def _wait_for(qapp, predicate, timeout_ms=6000):
    loop = QEventLoop()
    elapsed = {"ms": 0}

    def tick():
        elapsed["ms"] += 50
        if predicate() or elapsed["ms"] >= timeout_ms:
            loop.quit()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(50)
    loop.exec()
    timer.stop()
    return predicate()


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    return MainWindow()


# --- NetworkDialog (pure view) -----------------------------------------------


def test_dialog_defaults_to_loopback(qapp):
    from zlog.ui.network_dialog import NetworkDialog

    dlg = NetworkDialog()
    assert dlg.get_values() == ("127.0.0.1", 0)


def test_dialog_prefills_last_port(qapp):
    from zlog.ui.network_dialog import NetworkDialog

    dlg = NetworkDialog(last_port=5005)
    assert dlg.get_values() == ("127.0.0.1", 5005)


def test_dialog_remote_checkbox_binds_all_interfaces(qapp):
    from zlog.ui.network_dialog import NetworkDialog

    dlg = NetworkDialog()
    dlg.remote_check.setChecked(True)
    assert dlg.get_values()[0] == "0.0.0.0"


def test_dialog_rejects_invalid_port(qapp):
    from zlog.ui.network_dialog import NetworkDialog

    dlg = NetworkDialog()
    dlg.port_edit.setText("not-a-number")
    ok = dlg.buttons.button(QDialogButtonBox.Ok)
    ok.click()
    assert dlg.result() != QDialog.Accepted  # rejected, dialog stays open

    dlg.port_edit.setText("99999")  # out of range
    ok.click()
    assert dlg.result() != QDialog.Accepted


# --- window wiring -----------------------------------------------------------


def test_listen_network_starts_a_reader_and_resolves_port(qapp, window, monkeypatch):
    import zlog.ui.network_dialog as nd

    class FakeDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.Accepted

        def get_values(self):
            return ("127.0.0.1", 0)

    monkeypatch.setattr(nd, "NetworkDialog", FakeDialog)
    window.listen_network()
    try:
        reader = window._active.reader
        assert reader is not None
        assert _wait_for(qapp, lambda: window._active.stream_label != "tcp:127.0.0.1")
        assert window._active.stream_label.startswith("tcp:")
        assert window._active.stream_label != "tcp:0"  # resolved, not the raw request
    finally:
        window.stop()
    assert window._active.reader is None


def test_listen_network_cancelled_starts_nothing(window, monkeypatch):
    import zlog.ui.network_dialog as nd

    class FakeDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.Rejected

    monkeypatch.setattr(nd, "NetworkDialog", FakeDialog)
    window.listen_network()
    assert window._active.reader is None


def test_last_network_port_round_trips_through_settings(window):
    # `window`'s fixture already patches _settings_path (per-instance monkeypatch
    # persists for the whole test), so a second MainWindow() here reads/writes
    # the same settings file without any extra wiring.
    window._last_network_port = 5005
    window._save_settings()

    from zlog.ui.main_window import MainWindow

    w2 = MainWindow()
    try:
        w2._load_and_apply_settings()
        assert w2._last_network_port == 5005
    finally:
        w2.close()
