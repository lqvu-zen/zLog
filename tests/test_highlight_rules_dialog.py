"""Tests for the Highlight Rules dialog (view only, no MainWindow)."""

from __future__ import annotations


def test_dialog_reflects_initial_rules(qapp):
    from zlog.ui.highlight_rules_dialog import HighlightRulesDialog

    rules = [{"pattern": "boom", "regex": True, "color": "#ff0000"}]
    dlg = HighlightRulesDialog(rules)
    assert dlg.get_values() == rules


def test_add_and_remove_row(qapp):
    from zlog.ui.highlight_rules_dialog import HighlightRulesDialog

    dlg = HighlightRulesDialog([])
    dlg._add_row("crash", False, "#00ff00")
    assert dlg.get_values() == [{"pattern": "crash", "regex": False, "color": "#00ff00"}]
    dlg.table.selectRow(0)
    dlg._remove_selected()
    assert dlg.get_values() == []


def test_blank_pattern_row_is_dropped(qapp):
    from zlog.ui.highlight_rules_dialog import HighlightRulesDialog

    dlg = HighlightRulesDialog([])
    dlg._add_row("", False, "#ffeb3b")
    assert dlg.get_values() == []


def test_pick_color_updates_swatch(qapp, monkeypatch):
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog

    from zlog.ui.highlight_rules_dialog import HighlightRulesDialog

    monkeypatch.setattr(QColorDialog, "getColor", lambda **k: QColor("#123456"))
    dlg = HighlightRulesDialog([{"pattern": "x", "regex": False, "color": "#ffeb3b"}])
    dlg._pick_color(0)
    assert dlg.get_values()[0]["color"] == "#123456"
