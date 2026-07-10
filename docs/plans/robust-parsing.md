# Plan: Robust logcat parsing (multiple formats)

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v1.2 "Capture & scale" (Robust parsing), [save-load.md](save-load.md)

## Goal

After this ships, zLog parses the common `adb logcat` formats — `threadtime`
(default), `time`, `brief`, and `tag` — into structured entries (level / tag /
pid), instead of dumping non-threadtime lines raw into the message. Unrecognized
lines (banners, wrapped output) still fall back to raw text so nothing is dropped.

## Why

zLog streams with `-v threadtime`, but **opened** log files (File → Open) are
often captured elsewhere in a different format, and some tools/devices emit
variants. Today those show up as one raw blob per line with no level color, tag,
or PID — filters and colors don't work on them. Supporting the standard formats
makes opened logs first-class. This is pure `core/` work — Qt-free and unit-tested.

## Formats (tried most-specific first)

| Name | Example | Fields recovered |
|---|---|---|
| threadtime | `06-30 12:34:56.789  1234  5678 I Tag: msg` | time, pid, tid, level, tag, message |
| time | `06-30 12:34:56.789 I/Tag(  1234): msg` | time, level, tag, pid, message |
| brief | `I/Tag(  1234): msg` | level, tag, pid, message |
| tag | `I/Tag: msg` | level, tag, message |
| (fallback) | `--------- beginning of main` | message only (raw) |

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/parser.py` | core | Add compiled regexes `_TIME`, `_BRIEF`, `_TAG` alongside `_THREADTIME`. `parse_line` tries them in order (threadtime → time → brief → tag); the first match builds a `LogEntry` from whatever named groups are present (missing → `""`, tag stripped). No match → raw line in `message` (unchanged). Order matters: `brief` before `tag` so the `(pid)` isn't swallowed into the tag. |
| `tests/test_parser.py` | tests | Add cases for `time`, `brief`, and `tag` lines (fields recovered), confirm `brief` wins over `tag` for `(pid)` lines, and that existing threadtime + banner behavior is unchanged. |

## Architecture touch points

- **core/ stays Qt-free** and fully unit-tested; no `ui`/`adb` changes.
- **No streaming change:** live capture still uses `-v threadtime`; this only makes
  the parser tolerant of other inputs (mainly opened files).

## Risks & regressions to check

- **Pattern ordering / false matches:** threadtime lines start with a date, so the
  `tag`/`brief` patterns (which start with a level letter) can't steal them;
  `brief` must precede `tag`. Verify with tests.
- **Loose `tag` pattern:** `^[VDIWEF]/tag: msg` could match an odd message line, but
  such lines are raw today anyway and this only adds structure; acceptable.
- **Performance:** up to 4 regex tries per line; still trivial next to Qt paint, and
  threadtime (the live path) matches on the first try.

## Verification

- [ ] `uv run pytest` (new format tests + unchanged existing)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Spot-check: a small `brief`/`time` sample opened via File → Open shows colors,
      tags, and PID filtering working.
