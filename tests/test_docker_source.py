"""Docker container attach dialog and its window wiring (offscreen Qt).

`docker` itself is never spawned — the reader is faked the same way
tests/test_capture_controller.py fakes AdbReader/LaunchReader, so this suite
runs without Docker installed (see docs/plans/docker-log-source.md).
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from zlog.core.containers import Container


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    return MainWindow()


# --- DockerDialog (pure view) -----------------------------------------------


def test_docker_dialog_lists_containers_and_ok_gating(qapp):
    from zlog.ui.docker_dialog import DockerDialog

    containers = [Container("abc123", "web", "Up 5 minutes")]
    dlg = DockerDialog(containers, refresh=lambda: None)
    ok = dlg.buttons.button(QDialogButtonBox.Ok)
    assert ok.isEnabled() is True  # a container is preselected
    assert dlg.selected_container() == containers[0]


def test_docker_dialog_empty_list_disables_ok(qapp):
    from zlog.ui.docker_dialog import DockerDialog

    dlg = DockerDialog([], refresh=lambda: None)
    assert dlg.buttons.button(QDialogButtonBox.Ok).isEnabled() is False
    assert dlg.selected_container() is None


def test_docker_dialog_refresh_replaces_list(qapp):
    from zlog.ui.docker_dialog import DockerDialog

    calls = []
    dlg = DockerDialog([], refresh=lambda: calls.append(1))
    dlg._refresh()  # simulates clicking Refresh; the window supplies the real fetch
    assert calls == [1]
    dlg.set_containers([Container("x", "y", "Up 1 second")])
    assert dlg.selected_container().name == "y"


# --- window wiring -----------------------------------------------------------


class _FakeLaunchReader(QObject):
    """Same signal surface as the real LaunchReader — see
    tests/test_capture_controller.py's StubReader — but never spawns a process,
    so this runs without `docker` installed."""

    batch_ready = Signal(list)
    error = Signal(str)
    stream_ended = Signal()

    def __init__(self, argv, cwd=None):
        super().__init__()
        self.argv = list(argv)
        self.cwd = cwd
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        pass


def test_attach_docker_container_missing_shows_error(window, monkeypatch):
    import zlog.ui.docker_dialog as dd

    def raise_missing(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(dd, "list_containers", raise_missing)
    window.attach_docker_container()
    assert "docker not found" in window.statusBar().currentMessage()
    assert window._active.reader is None


def test_attach_docker_container_starts_reader(window, monkeypatch):
    import zlog.ui.docker_dialog as dd
    import zlog.winlog.launcher as launcher

    container = Container("abc123", "web", "Up 5 minutes")

    class FakeDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.Accepted

        def selected_container(self):
            return container

    monkeypatch.setattr(dd, "list_containers", lambda: [container])
    monkeypatch.setattr(dd, "DockerDialog", FakeDialog)
    monkeypatch.setattr(launcher, "LaunchReader", _FakeLaunchReader)

    window.attach_docker_container()

    reader = window._active.reader
    assert isinstance(reader, _FakeLaunchReader)
    assert reader.argv == ["docker", "logs", "-f", "abc123"]
    assert reader.started is True
    assert window._active.stream_label == "docker:web"


def test_attach_docker_container_cancel_starts_nothing(window, monkeypatch):
    import zlog.ui.docker_dialog as dd

    container = Container("abc123", "web", "Up 5 minutes")

    class FakeDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.Rejected

        def selected_container(self):
            return container

    monkeypatch.setattr(dd, "list_containers", lambda: [container])
    monkeypatch.setattr(dd, "DockerDialog", FakeDialog)

    window.attach_docker_container()
    assert window._active.reader is None
