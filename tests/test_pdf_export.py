import pytest

from zlog.core.export import to_print_html
from zlog.core.models import LogEntry
from zlog.ui.pdf_export import write_pdf


def _entries(n=1):
    return [
        LogEntry("06-30 12:00:00.000", "1", "2", "I" if i % 2 else "E", "Tag", f"line {i}")
        for i in range(n)
    ]


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    path = tmp_path / "settings.json"
    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: path)
    return MainWindow()


def test_write_pdf_creates_a_nonempty_file(qapp, tmp_path):
    html = to_print_html(_entries(5), title="t", generated="2026-01-01 00:00:00")
    path = tmp_path / "out.pdf"
    pages = write_pdf(html, str(path))
    assert pages >= 1
    assert path.exists()
    data = path.read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 100


def test_write_pdf_handles_empty_entries(qapp, tmp_path):
    html = to_print_html([], generated="2026-01-01 00:00:00")
    path = tmp_path / "empty.pdf"
    pages = write_pdf(html, str(path))
    assert pages >= 1
    assert path.exists()


def test_write_pdf_many_lines_paginates(qapp, tmp_path):
    html = to_print_html(_entries(2000), generated="2026-01-01 00:00:00")
    path = tmp_path / "big.pdf"
    pages = write_pdf(html, str(path))
    assert pages >= 2


def test_export_pdf_writes_filtered_entries(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    window.model.append_entries(_entries(3))
    out = tmp_path / "export.pdf"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))
    window._export_pdf()
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF")


def test_export_pdf_cancelled_save_dialog_writes_nothing(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    window.model.append_entries(_entries(3))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    window._export_pdf()  # must not raise despite no path chosen


def test_export_pdf_over_cap_prompts_and_respects_cancel(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw, "PDF_ROW_CAP", 5)
    window.model.append_entries(_entries(10))
    save_calls = []
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *a, **k: save_calls.append(1) or (str(tmp_path / "x.pdf"), ""),
    )
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Cancel)
    window._export_pdf()
    assert not save_calls  # cancelling the cap warning skips the save dialog entirely

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    window._export_pdf()
    assert save_calls == [1]
    assert (tmp_path / "x.pdf").exists()
