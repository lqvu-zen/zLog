"""Context-aware query-bar autocomplete — pure, no Qt, so it's unit-testable.

Given the query text + caret position (and the live tag/pid/process values seen in
the current log), decide which token is being typed and what to suggest for it:
field keys when starting a token, level names after ``level:``, and matching
tag/pid/process values after ``tag:``/``pid:``/``proc:``/``package:``. Each
suggestion is ``(value, description)`` where ``value`` is the *full replacement*
for the current token, so the UI just swaps the token span for it.
"""

from __future__ import annotations

from zlog.core.query import token_spans

# (name, letter) in ascending severity — completion offers the full names, which the
# parser accepts (level:error == level:E), each meaning "this level or higher".
_LEVELS = [
    ("verbose", "V"),
    ("debug", "D"),
    ("info", "I"),
    ("warn", "W"),
    ("error", "E"),
    ("fatal", "F"),
]

_PACKAGE_KEYS = {"package", "pkg", "app"}
_PROC_KEYS = {"proc", "process"}

# Field keys offered when starting a bare token (advertises the query syntax).
_FIELD_KEYS = [
    ("level:", "minimum severity (level:E = error or higher)"),
    ("tag:", "filter by log tag"),
    ("package:", "filter by app / package name"),
    ("pid:", "filter by process id"),
    ("proc:", "filter by process / package name"),
    ("since:", "only lines at/after HH:MM:SS"),
    ("until:", "only lines at/before HH:MM:SS"),
    ("device:", "filter by device (merged view)"),
]

_EXCLUDE_KEYS = [
    ("-pid:", "hide lines from a PID"),
    ("-proc:", "hide lines from a process"),
    ("-device:", "hide lines from a device"),
]


def current_token(text: str, cursor: int) -> tuple[int, int, str]:
    """Return ``(start, end, token)`` for the whitespace/quote-aware token the caret
    is in. When the caret sits in whitespace (starting a new token), returns an empty
    token at the caret."""
    for start, end, _kind in token_spans(text):
        if start <= cursor <= end:
            return start, end, text[start:end]
    return cursor, cursor, ""


def _kv(key: str, value: str) -> str:
    """`key:value`, quoting the value if it contains whitespace."""
    return f'{key}:"{value}"' if any(c.isspace() for c in value) else f"{key}:{value}"


def completions(
    text: str,
    cursor: int,
    tags: list[str] | tuple[str, ...] = (),
    procs: list[str] | tuple[str, ...] = (),
    pids: list[str] | tuple[str, ...] = (),
) -> tuple[int, int, list[tuple[str, str]]]:
    """Return ``(start, end, [(value, description), ...])`` for the current token.

    ``start``/``end`` bound the token to replace; each ``value`` is the full
    replacement text. Suggestions are prefix-filtered (case-insensitive) by what's
    already typed.
    """
    start, end, tok = current_token(text, cursor)

    if ":" in tok:
        key, _, val = tok.partition(":")
        keyl = key.lower()
        vlow = val.lstrip('"').lower()  # match the value part (ignore an opening quote)
        if keyl == "level":
            items = [
                (f"{key}:{name}", f"Filter by {letter} ({name.upper()}) or higher")
                for name, letter in _LEVELS
                if name.startswith(vlow)
            ]
        elif keyl == "tag":
            items = [(_kv(key, t), "tag") for t in tags if t.lower().startswith(vlow)]
        elif keyl == "pid":
            items = [(f"{key}:{p}", "PID") for p in pids if p.startswith(val)]
        elif keyl in _PROC_KEYS or keyl in _PACKAGE_KEYS:
            items = [(_kv(key, p), "process") for p in procs if p.lower().startswith(vlow)]
        else:
            items = []
        return start, end, items

    if tok.startswith("-"):
        pref = tok.lower()
        return start, end, [(v, d) for v, d in _EXCLUDE_KEYS if v.lower().startswith(pref)]

    pref = tok.lower()
    return start, end, [(v, d) for v, d in _FIELD_KEYS if v.lower().startswith(pref)]
