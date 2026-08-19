"""Tests for core/native_symbols.py — the .so resolution order, against a
fake filesystem (no real disk). See docs/plans/crash-symbolication.md.
"""

from __future__ import annotations

from zlog.core.native_symbols import find_symbol_file


def _fs(existing: set[str], recursive_matches: dict[str, list[str]] | None = None):
    exists = lambda p: p in existing  # noqa: E731
    matches = recursive_matches or {}
    glob_recursive = lambda root, lib: matches.get((root, lib), [])  # noqa: E731
    return exists, glob_recursive


def test_flat_match_wins_first():
    exists, glob_recursive = _fs({"/symbols/libfoo.so"})
    got = find_symbol_file("/symbols", "libfoo.so", None, exists, glob_recursive)
    assert got == "/symbols/libfoo.so"


def test_abi_subfolder_match_when_no_flat_match():
    exists, glob_recursive = _fs({"/symbols/arm64-v8a/libfoo.so"})
    got = find_symbol_file("/symbols", "libfoo.so", "arm64-v8a", exists, glob_recursive)
    assert got == "/symbols/arm64-v8a/libfoo.so"


def test_abi_subfolder_skipped_when_abi_unknown():
    exists, glob_recursive = _fs({"/symbols/arm64-v8a/libfoo.so"})
    got = find_symbol_file("/symbols", "libfoo.so", None, exists, glob_recursive)
    assert got is None


def test_unambiguous_recursive_match():
    exists, glob_recursive = _fs(
        set(),
        {("/symbols", "libfoo.so"): ["/symbols/deep/nested/libfoo.so"]},
    )
    got = find_symbol_file("/symbols", "libfoo.so", None, exists, glob_recursive)
    assert got == "/symbols/deep/nested/libfoo.so"


def test_ambiguous_recursive_matches_give_up_rather_than_guess():
    exists, glob_recursive = _fs(
        set(),
        {("/symbols", "libfoo.so"): ["/symbols/a/libfoo.so", "/symbols/b/libfoo.so"]},
    )
    got = find_symbol_file("/symbols", "libfoo.so", None, exists, glob_recursive)
    assert got is None


def test_no_match_anywhere_is_none():
    exists, glob_recursive = _fs(set())
    got = find_symbol_file("/symbols", "libfoo.so", "arm64-v8a", exists, glob_recursive)
    assert got is None


def test_empty_symbols_dir_short_circuits():
    exists, glob_recursive = _fs({"libfoo.so"})  # would match a "" join, but must not be tried
    got = find_symbol_file("", "libfoo.so", None, exists, glob_recursive)
    assert got is None


def test_flat_match_preferred_over_abi_and_recursive():
    exists, glob_recursive = _fs(
        {"/symbols/libfoo.so", "/symbols/arm64-v8a/libfoo.so"},
        {("/symbols", "libfoo.so"): ["/symbols/deep/libfoo.so"]},
    )
    got = find_symbol_file("/symbols", "libfoo.so", "arm64-v8a", exists, glob_recursive)
    assert got == "/symbols/libfoo.so"
