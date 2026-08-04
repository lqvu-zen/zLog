"""User-defined log formats: a `LogFormat` is a named regex (with named groups)
plus a level-alias map, so a project's own log can populate `LogEntry.level`/
`.time`/etc. and drive the same filters/colors/summaries logcat gets.

Pure, no Qt — compiled once per apply and handed to readers as read-only data
(see docs/plans/custom-log-format-editor.md). Follows core/extract.py's
compile-and-skip-invalid rule: a bad user regex must never crash a reader.
"""

from __future__ import annotations

import re
import time as _time
from dataclasses import dataclass
from re import Pattern

from zlog.core.models import LEVEL_RANK

# How many of a source's leading lines auto-detect samples before committing to
# a format — enough to skip past a banner or blank run, cheap even against a
# huge file since detection never reads past this many lines.
DETECT_SAMPLE_LINES = 200

# Length of the synthetic near-miss probe (see _build_probe). This runs
# synchronously on the UI thread on every keystroke while editing a pattern,
# and Python's `re` has no way to interrupt a match once started — so this
# number is a hard ceiling on how long a single preview update can ever take,
# not a tuning knob for "more signal". A classic catastrophic pattern like
# `(a+)+$` is roughly O(2^n) against a near-miss of length n: at 20 that's
# ~1e6 backtracking steps (comfortably under a second, still an obvious,
# clearly-different timing from a well-behaved pattern's sub-millisecond
# probe); going meaningfully higher risks turning the *safety check* itself
# into the freeze it's meant to warn about.
_PROBE_LENGTH = 20

# Regex escape letters that mean "a character class", not "the literal
# character" — 'd' in `\d+` isn't the literal digit d, so it must not be
# picked as the repeat seed below.
_ESCAPE_CLASS_LETTERS = frozenset("dDwWsSbBAZ")


@dataclass(frozen=True, slots=True)
class LogFormat:
    """One named parse pattern. `builtin=True` marks a read-only, code-defined
    entry (the four logcat patterns) as opposed to a user-authored one."""

    name: str
    pattern: str
    level_aliases: dict[str, str]
    builtin: bool = False


@dataclass(frozen=True, slots=True)
class CompiledFormat:
    """A `LogFormat` plus its compiled regex, ready for the per-line hot path —
    compile once, reuse for every line, never re-compile inside a read loop."""

    format: LogFormat
    regex: Pattern


def compile_formats(formats: list[LogFormat]) -> list[CompiledFormat]:
    """Compile each format's pattern, silently skipping one that doesn't
    compile — a bad user regex must degrade that one format, not crash the
    reader (same rule as `core/extract.py`)."""
    out: list[CompiledFormat] = []
    for f in formats:
        try:
            rx = re.compile(f.pattern)
        except re.error:
            continue
        out.append(CompiledFormat(f, rx))
    return out


def apply_aliases(level: str, aliases: dict[str, str]) -> str:
    """Canonicalize a captured level token. An explicit alias wins; a token
    that's already a canonical letter (V D I W E F) passes through unchanged;
    anything else is unparsed ("") — never a guess. An unmapped level must not
    silently become a fabricated severity."""
    if level in aliases:
        return aliases[level]
    if level in LEVEL_RANK:
        return level
    return ""


def detect_format(sample_lines: list[str], formats: list[CompiledFormat]) -> LogFormat | None:
    """Pick the format that matches the most sample lines, or `None` if there's
    no confident winner (nothing matched, or two formats tied) — the caller
    falls back to today's behaviour (built-ins only) on `None`."""
    if not sample_lines:
        return None
    scored: list[tuple[int, LogFormat]] = []
    for cf in formats:
        n = sum(1 for line in sample_lines if cf.regex.match(line))
        if n:
            scored.append((n, cf.format))
    if not scored:
        return None
    scored.sort(key=lambda t: t[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None  # a tie is not a confident pick
    return scored[0][1]


def _build_probe(pattern: str) -> str:
    """A synthetic near-miss line, built from the pattern's own literal
    characters where possible: repeat one, then break the match right at the
    end. Classic backtracking blowups (`(a+)+$` against a long run of `a`s
    that ends in something else) need the repeated run to actually contain
    the character the quantifier is chasing — a generic filler character
    (e.g. all `x`s) doesn't exercise that at all, since the engine has
    nothing to backtrack over. Falls back to `x` when the pattern has no
    plain literal to seed from (e.g. it's built entirely from `\\d`/`\\w`-style
    classes)."""
    without_escapes = re.sub(r"\\.", "", pattern)  # drop \d, \w, \\, etc. first
    seed = next((c for c in without_escapes if c.isalnum()), "x")
    if seed in _ESCAPE_CLASS_LETTERS:
        seed = "x"
    return seed * _PROBE_LENGTH + "!"


def time_pattern(pattern: str, sample_lines: list[str]) -> float:
    """Time one regex against the sample lines plus a synthetic near-miss
    (see `_build_probe`) — a line that matches cleanly runs fast even for a
    catastrophic pattern, so the near-miss is what actually exercises
    backtracking. Returns seconds; a compile failure returns 0.0 (the caller
    reports invalid-regex separately, not as "fast")."""
    try:
        rx = re.compile(pattern)
    except re.error:
        return 0.0
    started = _time.perf_counter()
    for line in (*sample_lines, _build_probe(pattern)):
        rx.match(line)
    return _time.perf_counter() - started


def parse_aliases_text(text: str) -> dict[str, str]:
    """Parse the dialog's one-`SPELLING=X`-per-line alias editor into a dict.
    Blank lines and anything without `=` are ignored rather than rejected, so
    the live preview stays responsive while a line is half-typed."""
    aliases: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        spelling, _, letter = line.partition("=")
        spelling = spelling.strip()
        letter = letter.strip().upper()
        if spelling and letter:
            aliases[spelling] = letter
    return aliases


def aliases_to_text(aliases: dict[str, str]) -> str:
    """Inverse of `parse_aliases_text`, for populating the editor from a stored
    format."""
    return "\n".join(f"{k}={v}" for k, v in aliases.items())


def formats_to_json(formats: list[LogFormat]) -> list[dict]:
    """Serialize user formats only — built-ins are code, not settings, so they
    round-trip by definition and never bloat the settings file."""
    return [
        {"name": f.name, "pattern": f.pattern, "level_aliases": dict(f.level_aliases)}
        for f in formats
        if not f.builtin
    ]


def formats_from_json(data: object) -> list[LogFormat]:
    """Rebuild user formats from stored JSON, skipping anything malformed —
    a hand-edited or corrupted settings file must not crash startup (same
    defensive shape as `core/theme_io.py`/`core/tabstate.py`)."""
    if not isinstance(data, list):
        return []
    out: list[LogFormat] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        pattern = str(item.get("pattern") or "")
        if not name or not pattern:
            continue
        raw_aliases = item.get("level_aliases")
        aliases = (
            {str(k): str(v) for k, v in raw_aliases.items()}
            if isinstance(raw_aliases, dict)
            else {}
        )
        out.append(LogFormat(name=name, pattern=pattern, level_aliases=aliases, builtin=False))
    return out


def resolve_format(name: str, formats: list[LogFormat]) -> LogFormat | None:
    """Look up a format by name (used to re-apply a tab's remembered choice
    without re-running detection)."""
    return next((f for f in formats if f.name == name), None)
