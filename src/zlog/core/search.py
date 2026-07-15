"""Build a text/regex matcher predicate — pure, no Qt."""

from __future__ import annotations

import re
from collections.abc import Callable


def compile_matcher(text: str, regex: bool, case: bool = False) -> Callable[[str], bool]:
    """Return a predicate that tests a haystack string.

    Empty ``text`` matches everything. When ``regex`` is True the text is compiled
    as a regular expression (raising ``re.error`` on an invalid pattern); otherwise
    it's a plain substring test. Both modes are case-insensitive by default; pass
    ``case=True`` for case-sensitive matching.
    """
    if not text:
        return lambda s: True
    if regex:
        pattern = re.compile(text, 0 if case else re.IGNORECASE)
        return lambda s: pattern.search(s) is not None
    if case:
        return lambda s: text in s
    needle = text.lower()
    return lambda s: needle in s.lower()


def find_spans(haystack: str, term: str, regex: bool, case: bool = False) -> list[tuple[int, int]]:
    """Return non-overlapping `(start, end)` spans where `term` matches within
    `haystack`. Empty `term` returns no spans (there's nothing to highlight).
    Same regex/case rules as `compile_matcher`; raises `re.error` on an invalid
    pattern.
    """
    if not term:
        return []
    if regex:
        pattern = re.compile(term, 0 if case else re.IGNORECASE)
        return [(m.start(), m.end()) for m in pattern.finditer(haystack)]
    hay = haystack if case else haystack.lower()
    needle = term if case else term.lower()
    spans: list[tuple[int, int]] = []
    start = 0
    while (idx := hay.find(needle, start)) != -1:
        spans.append((idx, idx + len(needle)))
        start = idx + len(needle)
    return spans
