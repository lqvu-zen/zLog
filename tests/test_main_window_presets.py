"""Filter presets through the window: save, apply, delete, and persist."""

from __future__ import annotations

import pytest


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    return MainWindow()


def _prompt(monkeypatch, name, ok=True):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: (name, ok))


def test_save_and_apply_preset(window, monkeypatch):
    # The query bar owns the filter; picking a level folds level:E into the query.
    window.query.setText("/FATAL|ANR/")
    window.level_box.setCurrentIndex(window.level_box.findData("E"))
    assert window.query.text() == "level:E /FATAL|ANR/"
    _prompt(monkeypatch, "Crashes")
    window.save_current_preset()

    assert [p["name"] for p in window._presets] == ["Crashes"]
    saved = window._presets[0]
    assert saved["min_level"] == "E" and saved["query"] == "level:E /FATAL|ANR/"

    # change filters, then re-apply the preset — the query comes back verbatim
    window.query.setText("")
    window._apply_preset(saved)
    assert window.level_box.currentData() == "E"
    assert window.query.text() == "level:E /FATAL|ANR/"
    # ...and the derived search/regex widgets follow from the query.
    assert window.regex_check.isChecked() is True
    assert window.search.text() == "FATAL|ANR"


def test_delete_preset(window, monkeypatch):
    _prompt(monkeypatch, "Temp")
    window.save_current_preset()
    assert window._presets
    window._delete_preset("Temp")
    assert window._presets == []


def test_save_update_button_reflects_state(window, monkeypatch):
    # Fresh, empty query: Save label, disabled (nothing to save).
    window._set_query_text("")
    window._refresh_save_update_button()
    assert window.save_update_btn.text() == "Save filter…"
    assert window.save_update_btn.isEnabled() is False

    # A non-empty unsaved query: still Save, now enabled.
    window.query.setText("tag:Activity")
    assert window.save_update_btn.text() == "Save filter…"
    assert window.save_update_btn.isEnabled() is True

    # Save it via the button -> becomes "Update <name>".
    _prompt(monkeypatch, "Acts")
    window._save_or_update_active()
    assert window.save_update_btn.text() == "Update Acts"
    assert window._active_preset_name == "Acts"


def test_button_update_rewrites_active_preset(window, monkeypatch):
    _prompt(monkeypatch, "P")
    window.query.setText("tag:A")
    window._save_or_update_active()  # creates P, now active
    # edit the query — button stays Update, so the edit can be saved back
    window.query.setText("tag:B -noise")
    assert window.save_update_btn.text() == "Update P"
    window._save_or_update_active()  # Update path
    saved = next(p for p in window._presets if p["name"] == "P")
    assert saved["query"] == "tag:B -noise"  # preset rewritten with the edits


def test_clearing_or_emptying_query_reverts_to_save(window, monkeypatch):
    _prompt(monkeypatch, "P")
    window.query.setText("tag:A")
    window._save_or_update_active()
    assert window.save_update_btn.text() == "Update P"

    window.query.setText("")  # user empties the bar -> detach
    assert window._active_preset_name is None
    assert window.save_update_btn.text() == "Save filter…"

    # re-apply, then Clear filters detaches too
    window._apply_preset(window._presets[0])
    assert window.save_update_btn.text() == "Update P"
    window.clear_filters()
    assert window._active_preset_name is None
    assert window.save_update_btn.text() == "Save filter…"


def test_deleting_active_preset_reverts_to_save(window, monkeypatch):
    _prompt(monkeypatch, "P")
    window.query.setText("tag:A")
    window._save_or_update_active()
    assert window.save_update_btn.text() == "Update P"
    window._delete_preset("P")
    assert window._active_preset() is None
    assert window.save_update_btn.text() == "Save filter…"


def _fake_dialog(monkeypatch, name, query, accepted=True):
    from PySide6.QtWidgets import QDialog

    import zlog.ui.main_window as mw

    class Fake:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.Accepted if accepted else QDialog.Rejected

        def get_values(self):
            return (name, query)

    monkeypatch.setattr(mw, "PresetDialog", Fake)


def test_add_preset_from_dialog(window, monkeypatch):
    _fake_dialog(monkeypatch, "Errors", "level:E -Gnss")
    window._add_preset()
    p = next(x for x in window._presets if x["name"] == "Errors")
    assert p["query"] == "level:E -Gnss"
    assert p["min_level"] == "E"  # parsed from the typed query


def test_add_preset_cancel_is_noop(window, monkeypatch):
    _fake_dialog(monkeypatch, "X", "tag:A", accepted=False)
    window._add_preset()
    assert window._presets == []


def test_edit_preset_rewrites_query_keeps_name(window, monkeypatch):
    from zlog.core.presets import make_preset, upsert_preset

    window._presets = upsert_preset([], make_preset("P", query="tag:A"))
    window._rebuild_presets_list()
    _fake_dialog(monkeypatch, "ignored-name", "tag:B -noise")
    window._edit_preset(window._presets[0])
    p = next(x for x in window._presets if x["name"] == "P")
    assert p["query"] == "tag:B -noise" and p["name"] == "P"  # name unchanged by Edit


def test_editing_active_preset_keeps_button_tracking(window, monkeypatch):
    _fake_dialog(monkeypatch, "P", "tag:A")
    window._add_preset()
    window._apply_preset(window._presets[0])  # P is now the active/tracked preset
    assert window.save_update_btn.text() == "Update P"
    _fake_dialog(monkeypatch, "P", "tag:Z")
    window._edit_preset(window._presets[0])
    assert window._active_preset_name == "P"
    assert window.save_update_btn.text() == "Update P"  # still tracked after edit


def test_clone_preset_duplicates_source(window, monkeypatch):
    from zlog.core.presets import make_preset, upsert_preset

    window._presets = upsert_preset([], make_preset("Base", query="tag:A -x"))
    window._rebuild_presets_list()
    # Clone dialog is seeded with the source query; user keeps a distinct name.
    _fake_dialog(monkeypatch, "Base copy", "tag:A -x")
    window._clone_preset(window._presets[0])
    names = {p["name"] for p in window._presets}
    assert names == {"Base", "Base copy"}  # original untouched, a new one added
    clone = next(p for p in window._presets if p["name"] == "Base copy")
    assert clone["query"] == "tag:A -x"


def test_preset_at_falls_back_to_selection(window, monkeypatch):
    from PySide6.QtCore import QPoint

    from zlog.core.presets import make_preset, upsert_preset

    window._presets = upsert_preset([], make_preset("Sel", query="tag:A"))
    window._rebuild_presets_list()
    window.presets_list.setCurrentRow(0)
    # A click that misses any row still resolves to the current selection.
    assert window._preset_at(QPoint(9999, 9999))["name"] == "Sel"


def test_presets_round_trip(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    w1 = MainWindow()
    w1.search.setText("timeout")
    _prompt(monkeypatch, "Net")
    w1.save_current_preset()

    w2 = MainWindow()
    w2._load_and_apply_settings()
    assert [p["name"] for p in w2._presets] == ["Net"]
    assert w2._presets[0]["search"] == "timeout"
