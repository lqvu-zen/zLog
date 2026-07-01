"""Build a text/regex matcher predicate — pure, no Qt."""

from __future__ import annotations

import re
from collections.abc import Callable


def compile_matcher(text: str, regex: bool) -> Callable[[str], bool]:
    """Return a predicate that tests a haystack string.

    Empty ``text`` matches everything. When ``regex`` is True the text is compiled
    as a case-insensitive regular expression (raising ``re.error`` on an invalid
    pattern); otherwise it's a plain case-insensitive substring test.
    """
    if not text:
        return lambda s: True
    if regex:
        pattern = re.compile(text, re.IGNORECASE)
        return lambda s: pattern.search(s) is not None
    needle = text.lower()
    return lambda s: needle in s.lower()
