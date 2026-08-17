"""Export/import of user-defined log formats through LogFormatDialog.

See docs/plans/log-format-export-import.md.
"""

from __future__ import annotations

import json

import pytest

from zlog.core.logformat import LogFormat, formats_from_json
from zlog.ui.log_format_dialog import LogFormatDialog

_BUILTIN = LogFormat(name="threadtime", pattern=r"^.*$", level_aliases={}, builtin=True)
_USER_A = LogFormat(
    name="MyProject",
    pattern=r"^(?P<time>\d+) \[(?P<level>\w+)\] (?P<message>.*)$",
    level_aliases={"ERROR": "E"},
)
_USER_B = LogFormat(name="Other", pattern=r"^(?P<message>.*)$", level_aliases={})


@pytest.fixture
def dialog(qapp):
    return LogFormatDialog([_BUILTIN, _USER_A])


def test_export_writes_only_user_formats(dialog, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    out = tmp_path / "formats.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))
    dialog._export()
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    restored = formats_from_json(data)
    assert restored == [_USER_A]  # builtin excluded


def test_export_cancelled_dialog_writes_nothing(dialog, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    out = tmp_path / "formats.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    dialog._export()
    assert not out.exists()


def _write_json(path, formats):
    from zlog.core.logformat import formats_to_json

    path.write_text(json.dumps(formats_to_json(formats)), encoding="utf-8")


def test_import_appends_a_new_format(dialog, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    src = tmp_path / "in.json"
    _write_json(src, [_USER_B])
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(src), ""))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    dialog._import()
    names = {f.name for f in dialog.get_values()}
    assert names == {"MyProject", "Other"}


def test_import_overwrites_a_same_named_format(dialog, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    updated = LogFormat(name="MyProject", pattern=r"^(?P<message>.*)$", level_aliases={})
    src = tmp_path / "in.json"
    _write_json(src, [updated])
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(src), ""))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    dialog._import()
    values = dialog.get_values()
    assert len(values) == 1
    assert values[0] == updated


def test_import_declined_confirmation_leaves_list_unchanged(dialog, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    src = tmp_path / "in.json"
    _write_json(src, [_USER_B])
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(src), ""))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Cancel)
    dialog._import()
    assert dialog.get_values() == [_USER_A]


def test_import_malformed_json_warns_and_leaves_list_unchanged(dialog, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    src = tmp_path / "in.json"
    src.write_text("not json{", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(src), ""))
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: warnings.append(a) or QMessageBox.Ok
    )
    dialog._import()
    assert len(warnings) == 1
    assert dialog.get_values() == [_USER_A]


def test_import_cancelled_open_dialog_does_nothing(dialog, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    dialog._import()
    assert dialog.get_values() == [_USER_A]


def test_import_updates_the_visible_list_widget(dialog, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    src = tmp_path / "in.json"
    _write_json(src, [_USER_B])
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(src), ""))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    dialog._import()
    labels = [dialog.list.item(i).text() for i in range(dialog.list.count())]
    assert "Other" in labels
