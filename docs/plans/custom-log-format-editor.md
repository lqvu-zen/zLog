# Plan: User-defined log formats

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-03
- **Related:** [custom-log-format-preset.md](custom-log-format-preset.md), [unparsed-level-hides-log.md](unparsed-level-hides-log.md), [regex-extract-columns.md](regex-extract-columns.md), [multi-line-entries.md](multi-line-entries.md), [robust-parsing.md](robust-parsing.md)

## Goal

A user can teach zLog their own log format — paste sample lines, write a
named-group regex, see it parse live — and every filter, color, and summary that
works on logcat then works on their log. zLog stops being Android-shaped.

Phase 2 of two. [custom-log-format-preset.md](custom-log-format-preset.md) proves
the mechanism against one real format; this generalizes it. The four built-in
logcat patterns and the phase-1 preset become entries in the same list as the
user's own — one code path, not two.

## Why

Today an unrecognized format degrades zLog to a text viewer: text search,
`/regex/`, `-exclude`, highlight rules, bookmarks and export still work, but the
Level dropdown, `level:`, `tag:`, `pid:`, `proc:`, `since:`/`until:`, level
colors, Tag Summary, crash/ANR detection and the jank summary all go dead. That's
roughly the half of zLog that makes it better than `tail -f`.

There's a near-miss already shipped. [regex-extract-columns.md](regex-extract-columns.md)
does named-group extraction from a message — but into *ad-hoc extra fields* shown
in the detail pane and a summary dialog. It can't populate `LogEntry.level` or
`.time`, so it can't drive the level gate or the time range. The machinery is
close; it's wired to the wrong destination. **Read that plan's `core/extract.py`
before writing a new extractor** — the compile-and-skip-invalid pattern there is
the right precedent and shouldn't be reinvented differently.

## Scope

- **In:** a `LogFormat` value type (name, regex, level aliases, timestamp hint); a
  pure matcher that tries an ordered list of formats; persistence; a manager
  dialog with a live preview against pasted sample lines; choosing which format
  applies to a source; the built-ins exposed as read-only entries.
- **Out (non-goals):** multi-line entries ([multi-line-entries.md](multi-line-entries.md)),
  auto-detecting the format by sniffing a file (see open questions), a
  point-and-click format builder for non-regex users, importing formats from
  log4j/logback/serilog config, JSON-lines logs (a different parse strategy — its
  own plan if wanted), and merging with `regex-extract-columns`' extra-field
  feature (they can coexist; unifying them is a later cleanup).

## Design

Keep the parse pure and the format list data. The current `_PATTERNS` tuple
becomes a default value rather than a hard-coded constant.

**Data shape** (`core/logformat.py`, new, Qt-free):

```python
@dataclass(frozen=True, slots=True)
class LogFormat:
    name: str                      # "MyProject", shown in the UI
    pattern: str                   # regex with named groups
    level_aliases: dict[str, str]  # {"ERROR": "E", "WARN": "W"}
    builtin: bool = False          # built-ins are read-only in the editor
```

Named groups use the canonical field names (`time`, `pid`, `tid`, `level`, `tag`,
`message`) — `parse_line` already builds from `m.groupdict()` by those names, so a
correctly-named pattern needs no new plumbing.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/logformat.py` (new) | core | `LogFormat`; `compile_formats(list[LogFormat])` skipping invalid regexes (like `core/extract.py` does) and reporting which failed; `apply_aliases(level, aliases)`; `formats_to_json`/`formats_from_json` for persistence (mirror `core/theme_io.py` and `core/tabstate.py`, which already solve exactly this). Pure, fully unit-tested. |
| `src/zlog/core/parser.py` | core | `parse_line(line, formats=None)` — `None` keeps today's built-in behaviour, so **all five existing call sites keep working unchanged** (`adb/reader.py:133`, `cli.py:61`, `core/session.py:35` and `:47`, `ui/file_follower.py:147`). The built-in logcat patterns get restated as `LogFormat(builtin=True)` entries so there's one representation, not two. |
| `src/zlog/core/settings.py` | core | `"log_formats": []` in `DEFAULTS` (user formats only; built-ins are code, not settings) and `"active_format": ""` (`""` = try all, current behaviour). |
| `src/zlog/ui/log_format_dialog.py` (new) | ui | The manager: list of formats, add/edit/remove/reorder, and — the part that makes this usable — a **live preview**: a sample-lines box on top, a parsed-fields table below, updating as the regex is typed, with invalid-regex feedback inline. Without the preview this feature is unusable by anyone who doesn't already debug regexes for fun. |
| `src/zlog/ui/main_window.py` | ui | A menu action to open the dialog; on apply, persist and re-parse. Per the rule in [main-window-drift.md](main-window-drift.md), keep this to construction + signal wiring — any real logic goes in the dialog module or `core/`. |
| `src/zlog/ui/log_model.py` or the readers | ui | Plumb the active format list to wherever `parse_line` is called (see open questions on *where* format choice lives). |
| `tests/test_logformat.py` (new) | — | Ordering (first match wins); invalid regex skipped, not crashing; aliases applied; unknown level → `""`; round-trip through JSON; a user format that shadows a built-in. |

**Re-parsing already-loaded rows.** Changing the format must update what's on
screen, or the preview lies. Cheapest correct approach: keep each entry's raw line
and re-run the parse over the master list, then `beginResetModel`/`endResetModel`
once. This is the **one** place a full model reset is legitimate — the
"never `beginResetModel` just to add lines" rule is about appends, and this isn't
an append. Note that `LogEntry` is frozen with `slots=True`, so re-parsing means
rebuilding the list, not mutating it.

## Architecture touch points

- **Threading:** unchanged. Parsing stays pure and on the reader thread; the
  format list is read-only data handed to the thread at start. **Don't** let a
  running reader reach back for the current format — pass it in, or apply format
  changes only to subsequent starts plus an explicit re-parse of loaded rows.
- **Model/proxy:** a re-parse resets the model (see above); the proxy's gates are
  untouched and simply start receiving populated fields.
- **Dependency direction:** `core/logformat.py` is Qt-free; the dialog is `ui`.
  `ui → core`, unchanged.

## Risks & regressions to check

- **A user format that shadows logcat.** If user formats are tried first, a loose
  pattern silently breaks Android parsing — the feature that already works. Try
  built-ins first by default, or make ordering explicit and visible in the dialog.
  Either way, test that a threadtime line still parses as threadtime with a
  greedy user format installed.
- **Catastrophic backtracking is now user-supplied.** A user regex with nested
  quantifiers, run over millions of lines on a reader thread, hangs the stream
  with no obvious cause. Mitigations to choose between: time the pattern against
  the sample in the preview and warn if it's slow; cap sample-preview work; and at
  minimum, make the failure diagnosable (the preview is where a user will notice).
  Python's `re` has no timeout — decide how far to go here before coding.
- **Invalid regex must never crash a reader.** Compile at apply time, report in
  the dialog, and skip bad entries — `core/extract.py` already establishes this.
- **Mis-parsing is worse than not parsing** — a half-matching pattern puts message
  text in `tag`. The preview is the defence; make it show the *full* parsed field
  values, not a truncated summary.
- **Level aliases that produce an unknown letter** must map to `""`, not a guess.
  No prerequisite is needed for this to be safe:
  `LogFilterProxy.filterAcceptsRow` guards its level checks with
  `if entry.level:`, so a level-less entry is exempt from both the exact-set and
  min-level branches and stays visible. (An earlier revision named
  [unparsed-level-hides-log.md](unparsed-level-hides-log.md) as a blocking
  prerequisite here — that was wrong; see that plan's investigation note. It is
  Done, and it does not gate this work.)
- **The preview is the only signal for a bad alias map.** A format whose regex
  matches but whose level tokens all fall through produces visible rows, no
  colors, and an inert Level dropdown — with no warning, since the status-bar
  note only fires when *nothing* parsed. Show the mapped level in the preview's
  parsed-fields table, not just the captured raw token, so a broken alias map is
  visible while the user is writing it.
- **Persistence round-trip**: a format with regex backslashes and quotes must
  survive JSON. Test with a genuinely nasty pattern, not `\d+`.
- **Don't regress the no-format path**: with no user formats and no active format,
  behaviour must be byte-identical to today. That's the `formats=None` default,
  and it deserves an explicit test.

## Verification

- [ ] With zero user formats configured, every existing parser test passes
      unchanged and a real logcat capture parses identically — the default path is
      untouched.
- [ ] Define a format in the dialog for a real non-logcat file: preview shows
      correct fields, apply → the open log re-parses, level colors appear, Level
      dropdown/`tag:`/`pid:`/`since:` all work.
- [ ] Invalid regex: dialog reports it inline; no crash; nothing is applied.
- [ ] A deliberately greedy user pattern does **not** break logcat parsing.
- [ ] Formats survive a restart (JSON round-trip) including a backslash-heavy
      pattern.
- [ ] A pathological regex against a large file: confirm what actually happens,
      and that the user can recover (this is the risk most likely to be discovered
      by a user rather than by us).
- [ ] `uv run pytest -q` in one process (CI's command) — local runs here are
      chunked across processes and are not the authoritative full-suite gate.
- [ ] `uv run ruff check .` / `ruff format --check .` clean.

## Open questions

- **Where does format choice live — global, per-tab, or per-source?** Per-tab is
  most useful (one tab on logcat, another on a project log) and fits the existing
  `core/tabstate.py`, which already persists per-tab query/level/package. Global
  is far simpler. **Decide before coding**, it shapes the plumbing.
- **Auto-detect on open?** Try each format against the first N lines and pick the
  best match. Nice, and it's how this becomes discoverable rather than a feature
  nobody finds — but it can pick wrong silently. Possible compromise: auto-detect,
  then say which format was chosen in the status bar so it's correctable.
- **Should this absorb `regex-extract-columns`' patterns?** They're solving
  adjacent problems with two mechanisms. Leaning no for now — unifying them is
  worthwhile but is a third plan, and doing it here doubles the blast radius.
- **How much protection against slow user regexes is worth building?** See risks.
