"""Parse the single query bar into filter parts — pure, no Qt, so it's testable.

Syntax (space-separated tokens; quote to include spaces):
    level:E            minimum level (V D I W E F, case-insensitive)
    tag:Activity       tag contains this text
    package:com.x      package (also `pkg:` / `app:`)
    -noise             exclude lines matching this text (repeatable)
    /re.*gex/          regex search over tag+message
    plain words        substring search over tag+message

Unknown `key:value` tokens are treated as plain search text so nothing is lost.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field

_LEVELS = {"V", "D", "I", "W", "E", "F"}
_PACKAGE_KEYS = {"package", "pkg", "app"}


@dataclass(frozen=True)
class QuerySpec:
    level: str | None = None
    tag: str = ""
    package: str = ""
    search: str = ""
    regex: bool = False
    excludes: tuple[str, ...] = field(default_factory=tuple)


def _tokenize(text: str) -> list[str]:
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def parse_query(text: str) -> QuerySpec:
    level: str | None = None
    tag = ""
    package = ""
    regex = False
    regex_body: str | None = None
    words: list[str] = []
    excludes: list[str] = []

    for tok in _tokenize(text):
        if not tok:
            continue
        if tok.startswith("-") and len(tok) > 1:
            excludes.append(tok[1:])
            continue
        if len(tok) >= 2 and tok.startswith("/") and tok.endswith("/"):
            regex_body = tok[1:-1]
            regex = True
            continue
        if ":" in tok:
            key, _, val = tok.partition(":")
            key = key.lower()
            if key == "level" and val and val[0].upper() in _LEVELS:
                level = val[0].upper()
                continue
            if key == "tag" and val:
                tag = val
                continue
            if key in _PACKAGE_KEYS and val:
                package = val
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
    )
