"""Tests for the query-history list — pure, no Qt."""

from zlog.core.history import normalize_history, push_history


def test_push_moves_to_front_and_dedupes():
    h = push_history([], "a")
    h = push_history(h, "b")
    h = push_history(h, "a")  # existing -> moves to front
    assert h == ["a", "b"]


def test_push_ignores_blank():
    assert push_history(["a"], "   ") == ["a"]


def test_push_caps():
    h = []
    for i in range(30):
        h = push_history(h, f"q{i}", limit=5)
    assert len(h) == 5 and h[0] == "q29"


def test_normalize_drops_junk():
    assert normalize_history(["a", "", 5, "a", "b"]) == ["a", "b"]
    assert normalize_history(None) == []
