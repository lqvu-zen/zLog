from PySide6.QtWidgets import QDialog

from zlog.core.theme import LIGHT
from zlog.ui.theme_editor import ThemeEditorDialog


def test_seeds_rows_from_base_theme(qapp):
    previews = []
    dlg = ThemeEditorDialog(LIGHT, previews.append)
    assert dlg._rows["window"].edit.text() == LIGHT.window
    assert dlg._rows["level_colors.W"].edit.text() == LIGHT.level_colors["W"]
    assert dlg._rows["level_text.E"].edit.text() == LIGHT.level_text["E"]


def test_editing_a_field_previews_and_updates_working_theme(qapp):
    previews = []
    dlg = ThemeEditorDialog(LIGHT, previews.append)
    dlg._rows["window"].set_color("#123456")
    assert dlg._theme.window == "#123456"
    assert previews[-1].window == "#123456"
    # other fields untouched
    assert dlg._theme.text == LIGHT.text


def test_editing_a_level_dict_field_only_changes_that_key(qapp):
    previews = []
    dlg = ThemeEditorDialog(LIGHT, previews.append)
    dlg._rows["level_colors.E"].set_color("#abcdef")
    assert dlg._theme.level_colors["E"] == "#abcdef"
    assert dlg._theme.level_colors["W"] == LIGHT.level_colors["W"]


def test_revert_restores_base_and_previews_it(qapp):
    previews = []
    dlg = ThemeEditorDialog(LIGHT, previews.append)
    dlg._rows["window"].set_color("#123456")
    dlg._revert()
    assert dlg._theme == LIGHT
    assert dlg._rows["window"].edit.text() == LIGHT.window
    assert previews[-1] == LIGHT


def test_cancel_previews_base_and_rejects(qapp):
    previews = []
    dlg = ThemeEditorDialog(LIGHT, previews.append)
    dlg._rows["window"].set_color("#123456")
    dlg._cancel()
    assert previews[-1] == LIGHT
    assert dlg.result() == QDialog.Rejected
    assert dlg.result_theme is None


def test_save_prompts_for_name_and_sets_result_theme(qapp, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("My Theme", True))
    dlg = ThemeEditorDialog(LIGHT, lambda t: None)
    dlg._rows["window"].set_color("#123456")
    dlg._save()
    assert dlg.result_theme.name == "My Theme"
    assert dlg.result_theme.window == "#123456"
    assert dlg.result() == QDialog.Accepted


def test_save_rejects_builtin_name_and_reprompts(qapp, monkeypatch):
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    calls = iter([("Dark", True), ("My Theme", True)])
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: next(calls))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    dlg = ThemeEditorDialog(LIGHT, lambda t: None)
    dlg._save()
    assert dlg.result_theme.name == "My Theme"


def test_save_cancelled_leaves_dialog_open(qapp, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("", False))
    dlg = ThemeEditorDialog(LIGHT, lambda t: None)
    dlg._save()
    assert dlg.result_theme is None
    assert dlg.result() == 0  # neither Accepted nor Rejected yet
