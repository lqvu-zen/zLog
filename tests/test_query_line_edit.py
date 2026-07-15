"""Smoke test for the query bar's token highlighting (paints without crashing)."""

from __future__ import annotations


def test_query_line_edit_paints_tokens(qapp):
    from zlog.ui.query_line_edit import QueryLineEdit

    w = QueryLineEdit()
    w.resize(420, 24)
    w.setText("level:E tag:Foo package:com.x -noise /re.*/ plain")
    w.grab()  # forces paintEvent; must not raise
    # empty text path is safe too
    w.setText("")
    w.grab()
