# Plan: Built-in preset for a custom project log format

- **Status:** Draft — optional follow-up to [custom-log-format-editor.md](custom-log-format-editor.md); **blocked on input** (see below)
  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-03
- **Related:** [custom-log-format-editor.md](custom-log-format-editor.md), [unparsed-level-hides-log.md](unparsed-level-hides-log.md), [robust-parsing.md](robust-parsing.md), [multi-line-entries.md](multi-line-entries.md)

## Goal

One specific non-logcat format — a log from another project — parses out of the
box, with no user configuration, into real `time`/`pid`/`level`/`tag`/`message`
fields.

## Read this first: do the editor instead

**This plan is optional, and it should not be done before
[custom-log-format-editor.md](custom-log-format-editor.md).**

It was originally written as "phase 1 of two", on the reasoning that a single
hard-coded pattern is cheap and ships value while the editor gets designed. Two
things killed that argument:

1. **This is the blocked plan; the editor isn't.** This one can't start until the
   format's owner supplies sample lines. The editor depends on nothing unbuilt.
   Sequencing the blocked work first stalls everything.
2. **Once the editor exists, most of this evaporates.** Adding a format stops
   being parser work and becomes a data entry in a built-in list — the regex, the
   alias map, and a name. The editor's live preview is also a far better way to
   *develop* the pattern than writing it blind against sample lines in a test
   file.

**What remains worth doing afterwards**, and it's genuinely not nothing:

- **Zero-config for the team.** If several people use zLog against this format,
  shipping it as a default means nobody writes a regex or imports anything.
- **A non-logcat built-in.** Gives the editor's list a worked example that isn't
  Android-shaped, which is a better starting point for someone writing their own.

Neither is urgent. Treat this as "promote a proven format to a shipped default"
once the editor has been used to get the pattern right — at which point the
design below is mostly reference for *where* the pattern goes.

## Required input — this plan cannot be implemented without it

The implementer needs, from the format's owner:

1. **5–10 representative lines**, verbatim, including the awkward ones:
   a normal line, the longest realistic line, a line whose message contains the
   field delimiter, and a startup/banner line if the format has one.
2. **The level vocabulary** — every spelling that appears (`ERROR`/`ERR`/`E`,
   `WARN`/`WARNING`, `TRACE`, numeric codes) and how many distinct levels exist.
   If the format has **no** severity field, say so: the level filter cannot be
   made to work and this plan should record that rather than fake it.
3. **The timestamp format** — including whether it has a date, sub-second
   precision, and a timezone.
4. **Whether entries ever span multiple lines** (stack traces, pretty-printed
   payloads). If yes, read [multi-line-entries.md](multi-line-entries.md) first —
   it's a materially larger change and this plan deliberately does not cover it.

Do not guess these from a single sample line. A regex built from one example is
the classic way to silently mis-parse 5% of a log, and mis-parsed is worse than
unparsed — an unparsed line at least shows its full text.

If the editor has already shipped, this requirement softens considerably: the
pattern gets developed interactively against a real file in the preview, and what
lands here is a pattern already known to work rather than one derived from a
handful of pasted lines.

## Why this shape

`parse_line` already tries four logcat variants in order and falls back to putting
the raw line in `message`. Adding one more pattern is a small change to a pure,
70-line, fully-tested module — no dialog, no settings key, no persistence.

If [custom-log-format-editor.md](custom-log-format-editor.md) has landed first
(recommended), the shape changes: `_PATTERNS` will already have become a list of
`LogFormat` values, so this becomes **one more `LogFormat(builtin=True)` entry**
plus its tests, not a new regex constant wired into `parse_line`. Same outcome,
less code, and the ordering rules below still apply verbatim.

## Scope

- **In:** one new compiled pattern in `core/parser.py`; a level-alias map so
  `ERROR` → `E`; a timestamp normalization if the format's timestamp doesn't
  already sort lexicographically; tests built from the real sample lines.
- **Out (non-goals):** any UI, user-editable formats
  ([custom-log-format-editor.md](custom-log-format-editor.md)), multi-line
  entries ([multi-line-entries.md](multi-line-entries.md)), per-tab format
  selection (the editor plan owns that), and changing how the existing logcat
  patterns behave.

## Design

One pattern, added to the existing ordered tuple. The ordering rule that already
governs `_BRIEF` before `_TAG` applies: **most specific first.**

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/parser.py` | core | A new `_PROJECT` pattern with named groups matching the canonical field names (`time`, `pid`, `tid`, `level`, `tag`, `message`) — `parse_line` already reads `m.groupdict()` by those names, so a correctly-named pattern needs **no** changes to the function body. Add it to `_PATTERNS` in the right position (see risks). |
| `src/zlog/core/parser.py` | core | A `_LEVEL_ALIASES: dict[str, str]` mapping the format's spellings to the canonical `V D I W E F` letters, applied to the captured `level` before constructing the `LogEntry`. This is the one behaviour change to `parse_line`'s body, and it's a single `.get(x, x)` lookup — keep it that small. Unknown spellings map to `""` (unparsed level), **not** to a guess. |
| `src/zlog/core/models.py` | core | Only if the format's levels don't map onto `V D I W E F` — e.g. it has a distinct `TRACE` below Verbose. Prefer mapping onto the existing six; extending `LEVEL_RANK` touches severity navigation, heat marks, the sparkline, and the Level dropdown, which is a much wider blast radius than it looks. |
| `tests/test_parser.py` | — | One test per sample line, asserting every field — not just that it matched. Plus: a line the pattern must **not** match (proving it doesn't cannibalize logcat lines), and a malformed variant falling back to raw-in-`message`. |

**No other file changes.** All five `parse_line` call sites — `adb/reader.py:133`,
`cli.py:61`, `core/session.py:35` and `:47`, `ui/file_follower.py:147` — pick the
new format up for free, which means opened files, followed files, the CLI, and
even adb output all benefit without being touched.

**One source that does *not* benefit, and it matters:** `winlog/launcher.py`
builds its `LogEntry` directly (`_entry`, line 117) and never calls `parse_line`.
It stamps `time=now`, `pid=<child pid>`, `tag=<exe name>`, and guesses
`level=infer_level(text)` from keywords. So if the other project is a Windows app
**launched from zLog**, its own timestamps and levels are discarded and the whole
line lands in `message` — worse than following its log file. If that's the
intended workflow, routing `LaunchReader` through `parse_line` (falling back to
the current stamping when nothing matches) belongs in this plan; decide before
implementing, because it changes the file list.

## Architecture touch points

- **Threading:** none. `parse_line` is pure and already called from every reader
  thread; adding a pattern doesn't change that contract.
- **Model/proxy:** none directly — but this is the point of the change: entries
  now arrive with real `level`/`tag`/`time`, so the existing proxy gates start
  working on this format.
- **Dependency direction:** entirely within `core/`. No Qt.

## Risks & regressions to check

- **Pattern ordering is the main hazard.** `_PATTERNS` is tried in order, first
  match wins. A loose new pattern placed early will swallow logcat lines and
  silently corrupt Android parsing — the most damaging possible regression here,
  because it degrades the feature that already works. Add the new pattern **after**
  the four logcat ones unless a sample proves it must precede them, and test that
  a threadtime line still parses as threadtime.
- **Anchor the pattern.** `^…$` with specific field shapes (`\d`, explicit
  separators), not `.*` between groups. A greedy pattern matches things it
  shouldn't.
- **Mis-parsing is worse than not parsing.** A line that half-matches puts part of
  the message in `tag` and loses the rest. Every sample line's *full* message must
  round-trip exactly.
- **Catastrophic backtracking**: nested quantifiers in a regex run against every
  line of a multi-million-line file will hang the reader thread. Keep the pattern
  linear; if in doubt, time it against a large file.
- **Unknown level spellings must not become a guess.** Mapping an unrecognized
  token to `I` invents severity. Map to `""` instead. This is safe today and
  needs no prerequisite: `LogFilterProxy.filterAcceptsRow` guards its level
  checks with `if entry.level:`, so an entry with no level is exempt from both
  the exact-set and min-level branches and stays visible regardless of the
  Level dropdown. (An earlier revision of this plan claimed the opposite and
  named [unparsed-level-hides-log.md](unparsed-level-hides-log.md) as a
  blocking prerequisite — that was wrong; see that plan's investigation note.
  It is now Done and unrelated to sequencing here.)
- **But an all-unmapped format is still a bad outcome**, just a quieter one:
  every row visible, no level colors, Level dropdown inert. The status-bar note
  from `unparsed-level-hides-log.md` fires only when *nothing* parsed, so a
  format that matches but whose levels all fall through gets no warning at all.
  Check the alias map against the real level vocabulary rather than relying on
  a runtime signal.
- **Don't extend `LEVEL_RANK` casually** (see the table note).

## Verification

- [ ] Every supplied sample line parses with **all** fields correct — asserted
      field-by-field, not just "matched".
- [ ] The full sample file opens in the real UI: level colors correct, Level
      dropdown filters, `tag:` and `pid:` work, `since:`/`until:` bound correctly,
      Tag Summary lists real tags.
- [ ] **Logcat regression:** the existing `tests/test_parser.py` suite passes
      untouched, and a real device capture still parses — the new pattern must not
      have stolen any logcat line.
- [ ] A deliberately malformed line falls back to raw-in-`message` (nothing
      dropped) rather than half-matching.
- [ ] Timing against a large real file (≥100k lines) — no visible slowdown vs.
      before, confirming no backtracking blowup.
- [ ] `uv run pytest -q` in one process (CI's command); local runs here are
      chunked and are not the full-suite gate.
- [ ] `uv run ruff check .` / `ruff format --check .` clean.

## Open questions

- **Route `LaunchReader` through `parse_line`?** See the Design note. Depends on
  whether the other project is launched from zLog or writes a file. This is the
  one open decision that changes the scope of the plan.
- **Is the timestamp comparable?** `since:`/`until:` and the timeline histogram
  assume timestamps sort. If the format uses e.g. `03/Aug/2026:14:22:01`, it needs
  normalizing to the canonical shape at parse time — cheap here, expensive later.
- **Does the format carry a thread id?** If not, leave `tid=""`; `LogEntry.pidtid`
  already handles a missing tid gracefully (added for the Windows sources).
