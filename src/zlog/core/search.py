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
