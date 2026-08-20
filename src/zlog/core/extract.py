"""Extract ad-hoc fields from a log message — either via user regexes with
named groups, or by auto-detecting an embedded JSON object — pure, no Qt, so
both are unit-testable. See docs/plans/json-field-filter.md.

A pattern like ``latency=(?P<ms>\\d+)ms`` pulls a `ms` field out of every matching
line. Invalid patterns are skipped (never raised) so one bad entry can't break the
whole set; the first match wins per group name across the pattern list.
"""

from __future__ import annotations

import json
import re
from re import Pattern


def compile_extractors(patterns: list[str]) -> list[Pattern]:
    """Compile each pattern, dropping any that don't compile or have no named
    groups (a pattern with no `(?P<name>…)` extracts nothing)."""
    compiled: list[Pattern] = []
    for p in patterns:
        if not p:
            continue
        try:
            rx = re.compile(p)
        except re.error:
            continue
        if rx.groupindex:  # has at least one named group
            compiled.append(rx)
    return compiled


def extract(message: str, patterns: list[Pattern]) -> dict[str, str]:
    """Return `{group_name: value}` from the first match of each pattern.

    Groups already filled by an earlier pattern are not overwritten (first match
    wins). Non-matching patterns and unmatched optional groups contribute nothing.
    """
    fields: dict[str, str] = {}
    for rx in patterns:
        m = rx.search(message)
        if not m:
            continue
        for name, value in m.groupdict().items():
            if value is not None and name not in fields:
                fields[name] = value
    return fields


def extract_json(message: str) -> dict[str, str]:
    """Parse a JSON object embedded in `message` into `{key: str(value)}`
    pairs, flattened one level for nested objects (`{"a": {"b": 1}}` ->
    `{"a.b": "1"}`). Returns `{}` for anything that isn't a JSON object —
    never raises, and never guesses at a malformed line.

    Tries the whole (stripped) message first; if that isn't valid JSON, falls
    back to the first balanced `{...}` substring, so a line like
    `INFO: request done {"status": 200}` still gets read.
    """
    obj = _try_json_object(message.strip())
    if obj is None:
        start = message.find("{")
        if start >= 0:
            obj = _first_balanced_object(message, start)
    return _flatten(obj) if isinstance(obj, dict) else {}


def _try_json_object(text: str):
    # Split into two except clauses on purpose — the installed ruff formatter
    # mangles a parenthesized `except (ValueError, TypeError)` tuple into
    # invalid `except ValueError, TypeError` syntax (see core/settings.py's
    # load_settings for the same workaround).
    try:
        return json.loads(text)
    except ValueError:
        return None
    except TypeError:
        return None


def _first_balanced_object(text: str, start: int):
    """The first `{...}` substring starting at `start` with balanced braces,
    parsed as JSON — or None if the braces never balance (a truncated line)."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return _try_json_object(text[start : i + 1])
    return None


def _flatten(obj: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in obj.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            out.update(_flatten(value, name))
        elif isinstance(value, bool):
            out[name] = "true" if value else "false"
        elif value is None:
            out[name] = "null"
        else:
            out[name] = str(value)
    return out
