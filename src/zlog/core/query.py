"""Parse the single query bar into filter parts — pure, no Qt, so it's testable.

Syntax (space-separated tokens; quote to include spaces):
    level:E            minimum level — a letter (V D I W E F) or full name
                       (Verbose/Debug/Info/Warn(ing)/Error/Fatal), case-insensitive
    tag:Activity       tag contains this text
    package:com.x      package (also `pkg:` / `app:`)
    pid:1234           only this PID (comma-set: pid:100,200)
    proc:com.x         resolved process/package name contains this (also `process:`)
    since:HH:MM:SS     only lines at/after this time-of-day (inclusive)
    until:HH:MM:SS     only lines at/before this time-of-day (inclusive)
    -noise             exclude lines matching this text (repeatable)
    /re.*gex/          regex search over tag+message
    plain words        substring search over tag+message

Unknown `key:value` tokens are treated as plain search text so nothing is lost.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field

# Every accepted level: spelling (letter or full name), lowercased -> letter.
_LEVEL_ALIASES = {
    "v": "V",
    "verbose": "V",
    "d": "D",
    "debug": "D",
    "i": "I",
    "info": "I",
    "w": "W",
    "warn": "W",
    "warning": "W",
    "e": "E",
    "error": "E",
    "f": "F",
    "fatal": "F",
}
_PACKAGE_KEYS = {"package", "pkg", "app"}
_PROC_KEYS = {"proc", "process"}


def _parse_level_token(val: str) -> list[str]:
    """Parse a `level:` token's value into recognized level letters — each
    comma-separated part is a letter or a full name, case-insensitive.
    Unrecognized parts are dropped (the caller treats an empty result as "no
    match", falling back to plain search text)."""
    letters = []
    for part in val.split(","):
        letter = _LEVEL_ALIASES.get(part.strip().lower())
        if letter:
            letters.append(letter)
    return letters


@dataclass(frozen=True)
class QuerySpec:
    level: str | None = None
    tag: str = ""
    package: str = ""
    search: str = ""
    regex: bool = False
    excludes: tuple[str, ...] = field(default_factory=tuple)
    levels: tuple[str, ...] = field(default_factory=tuple)  # exact set (level:W,E)
    pids: tuple[str, ...] = field(default_factory=tuple)  # exact PID set (pid:100,200)
    process: str = ""  # process/package-name contains (proc:com.foo)
    exclude_pids: tuple[str, ...] = field(default_factory=tuple)  # -pid:100,200
    exclude_process: str = ""  # -proc:com.foo (last token wins, mirrors `process`)
    since: str = ""  # since:HH:MM:SS — raw value, parsed by the caller
    until: str = ""  # until:HH:MM:SS — raw value, parsed by the caller


def _tokenize(text: str) -> list[str]:
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def parse_query(text: str) -> QuerySpec:
    level: str | None = None
    levels: list[str] = []
    tag = ""
    package = ""
    process = ""
    pids: list[str] = []
    exclude_process = ""
    exclude_pids: list[str] = []
    since = ""
    until = ""
    regex = False
    regex_body: str | None = None
    words: list[str] = []
    excludes: list[str] = []

    for tok in _tokenize(text):
        if not tok:
            continue
        if tok.startswith("-") and len(tok) > 1:
            body = tok[1:]
            if ":" in body:
                key, _, val = body.partition(":")
                key = key.lower()
                if key == "pid" and val:
                    for part in val.split(","):
                        part = part.strip()
                        if part.isdigit():
                            exclude_pids.append(part)
                    continue
                if key in _PROC_KEYS and val:
                    exclude_process = val
                    continue
            excludes.append(body)
            continue
        if len(tok) >= 2 and tok.startswith("/") and tok.endswith("/"):
            regex_body = tok[1:-1]
            regex = True
            continue
        if ":" in tok:
            key, _, val = tok.partition(":")
            key = key.lower()
            if key == "level" and val:
                letters = _parse_level_token(val)
                if letters:
                    if "," in val or len(letters) > 1:
                        levels = list(dict.fromkeys(letters))  # exact set
                    else:
                        level = letters[0]  # minimum-level floor
                    continue
            if key == "tag" and val:
                tag = val
                continue
            if key in _PACKAGE_KEYS and val:
                package = val
                continue
            if key in _PROC_KEYS and val:
                process = val
                continue
            if key == "pid" and val:
                for part in val.split(","):
                    part = part.strip()
                    if part.isdigit():
                        pids.append(part)
                continue
            if key == "since" and val:
                since = val
                continue
            if key == "until" and val:
                until = val
                continue
        words.append(tok)

    search = regex_body if regex_body is not None else " ".join(words)
    return QuerySpec(
        level=level,
        tag=tag,
        package=package,
        search=search,
        regex=regex,
        excludes=tuple(excludes),
        levels=tuple(levels),
        pids=tuple(dict.fromkeys(pids)),
        process=process,
        exclude_pids=tuple(dict.fromkeys(exclude_pids)),
        exclude_process=exclude_process,
        since=since,
        until=until,
    )


def _classify(token: str) -> str:
    """Classify a raw query token for syntax highlighting."""
    if len(token) >= 2 and token.startswith("/") and token.endswith("/"):
        return "regex"
    if token.startswith("-") and len(token) > 1:
        return "exclude"
    if ":" in token:
        key = token.split(":", 1)[0].lower()
        if key == "level":
            return "level"
        if key == "tag":
            return "tag"
        if key in _PACKAGE_KEYS:
            return "package"
        if key in _PROC_KEYS:
            return "proc"
        if key == "pid":
            return "pid"
        if key in ("since", "until"):
            return "time"
    return "word"


def token_spans(text: str) -> list[tuple[int, int, str]]:
    """Return ``(start, end, kind)`` for each whitespace-separated token in `text`.

    A quote-aware scanner keeps `"two words"` as one token. `kind` is one of
    level/tag/package/proc/pid/exclude/regex/word — pure, so it's unit-testable and
    drives the query bar's token highlighting.
    """
    spans: list[tuple[int, int, str]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        start = i
        in_quote = False
        while i < n and (in_quote or not text[i].isspace()):
            if text[i] == '"':
                in_quote = not in_quote
            i += 1
        spans.append((start, i, _classify(text[start:i])))
    return spans
