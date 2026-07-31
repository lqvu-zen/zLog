"""The one-time "fetch adb for me" prompt and its wiring into MainWindow (see
docs/plans/bundle-adb.md). Never touches the network or a real dialog — adb
resolution and the prompt's own choice are both monkeypatched.
"""

from __future__ import annotations

import shutil

import pytest
from PySide6.QtCore import QThread, Signal


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    # Deterministic "adb resolves to nothing" starting point, regardless of
    # whatever this test machine actually has on PATH.
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(MainWindow, "_managed_adb", lambda self: None)
    return MainWindow()


def _fail_with_missing_adb(*_a, **_k):
    raise FileNotFoundError()


def test_prompt_fires_on_user_initiated_action_when_adb_resolves_nowhere(window, monkeypatch):
    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw, "list_devices", _fail_with_missing_adb)
    calls = []
    monkeypatch.setattr(mw, "ask_adb_setup", lambda parent: calls.append(1) or "later")

    window.refresh_devices()  # user_initiated=True by default — this is a Refresh click

    assert calls == [1]
    assert window._adb_setup_asked is True


def test_prompt_never_fires_at_cold_start(qapp, tmp_path, monkeypatch):
    """__init__'s own refresh_devices() call must stay silent even with no adb
    anywhere — see usable-without-adb.md's "cold start stays silent" rule,
    which this prompt must not violate."""
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(MainWindow, "_managed_adb", lambda self: None)
    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw, "list_devices", _fail_with_missing_adb)
    calls = []
    monkeypatch.setattr(mw, "ask_adb_setup", lambda parent: calls.append(1) or "later")

    MainWindow()  # __init__ calls refresh_devices(user_initiated=False)

    assert calls == []


def test_prompt_asked_at_most_once(window, monkeypatch):
    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw, "list_devices", _fail_with_missing_adb)
    calls = []
    monkeypatch.setattr(mw, "ask_adb_setup", lambda parent: calls.append(1) or "later")

    window.refresh_devices()
    window.refresh_devices()
    window.refresh_devices()

    assert calls == [1]  # not re-asked on every subsequent failure


def test_prompt_skipped_when_something_already_resolves(window, monkeypatch):
    """A guard independent of the caller's own "missing" classification: if
    adb actually resolves (e.g. found on PATH after all), never offer to fetch
    a redundant copy."""
    import zlog.ui.main_window as mw

    monkeypatch.setattr(shutil, "which", lambda name: "C:/real/adb.exe")
    calls = []
    monkeypatch.setattr(mw, "ask_adb_setup", lambda parent: calls.append(1) or "later")

    window._maybe_offer_adb_setup()

    assert calls == []
    assert window._adb_setup_asked is False


def test_prompt_skipped_but_marked_asked_on_unsupported_os(window, monkeypatch):
    """Fetching isn't offered off Windows (see bundle-adb.md scope) — no
    dialog, but still marked asked so nothing keeps re-checking every time."""
    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw.sys, "platform", "linux")
    calls = []
    monkeypatch.setattr(mw, "ask_adb_setup", lambda parent: calls.append(1) or "later")

    window._maybe_offer_adb_setup()

    assert calls == []
    assert window._adb_setup_asked is True


def test_fetch_choice_starts_the_download(window, monkeypatch):
    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw.sys, "platform", "win32")
    monkeypatch.setattr(mw, "ask_adb_setup", lambda parent: mw.FETCH)
    started = []
    monkeypatch.setattr(window, "_start_adb_fetch", lambda url, sha: started.append((url, sha)))

    window._maybe_offer_adb_setup()

    from zlog.core.adbfetch import expected_sha256, platform_tools_url

    assert started == [(platform_tools_url("win32"), expected_sha256("win32"))]


def test_manual_choice_opens_the_download_page(window, monkeypatch):
    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw.sys, "platform", "win32")
    monkeypatch.setattr(mw, "ask_adb_setup", lambda parent: mw.MANUAL)
    opened = []
    monkeypatch.setattr(
        mw.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url))
    )

    window._maybe_offer_adb_setup()

    assert len(opened) == 1 and opened[0].toString() == mw.DOWNLOAD_PAGE


def test_settings_download_button_bypasses_the_asked_gate(window, monkeypatch):
    """Settings -> Download adb... is a direct action, not the one-shot
    intent prompt — it must work even after the prompt was already asked."""
    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw.sys, "platform", "win32")
    window._adb_setup_asked = True
    started = []
    monkeypatch.setattr(window, "_start_adb_fetch", lambda url, sha: started.append((url, sha)))

    window._download_adb_from_settings()

    assert len(started) == 1


def test_settings_download_button_off_windows_opens_link_instead(window, monkeypatch):
    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw.sys, "platform", "linux")
    opened = []
    monkeypatch.setattr(
        mw.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url))
    )
    started = []
    monkeypatch.setattr(window, "_start_adb_fetch", lambda url, sha: started.append(1))

    window._download_adb_from_settings()

    assert started == [] and len(opened) == 1


def test_start_adb_fetch_refuses_a_concurrent_second_fetch(window, monkeypatch):
    window._adb_fetcher = object()  # something already in flight
    window._start_adb_fetch("http://x", "hash")
    assert "Already downloading" in window.statusBar().currentMessage()


class _FakeFetcher(QThread):
    progress = Signal(int, int)
    done = Signal(str)
    error = Signal(str)

    def __init__(self, url, sha256, dest_dir, parent=None):
        super().__init__(parent)
        self.url, self.sha256, self.dest_dir = url, sha256, dest_dir

    def cancel(self) -> None:
        pass

    def start(self, *a, **k):
        self.progress.emit(50, 100)
        self.done.emit("C:/fake/platform-tools/adb.exe")


class _FakeFailingFetcher(_FakeFetcher):
    def start(self, *a, **k):
        self.error.emit("Downloaded file failed verification — nothing was installed.")


def test_start_adb_fetch_success_refreshes_devices(window, monkeypatch):
    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw, "AdbFetcher", _FakeFetcher)
    refreshed = []
    monkeypatch.setattr(window, "refresh_devices", lambda **k: refreshed.append(k))

    window._start_adb_fetch("http://x", "hash")

    assert window.statusBar().currentMessage() == "adb installed."
    assert refreshed == [{}]
    assert window._adb_fetcher is None  # cleared after finishing


def test_start_adb_fetch_error_reports_and_clears(window, monkeypatch):
    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw, "AdbFetcher", _FakeFailingFetcher)

    window._start_adb_fetch("http://x", "hash")

    assert "failed verification" in window.statusBar().currentMessage()
    assert window._adb_fetcher is None
