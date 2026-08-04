# Plan: User-defined log formats

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-03
- **Related:** [custom-log-format-preset.md](custom-log-format-preset.md), [unparsed-level-hides-log.md](unparsed-level-hides-log.md), [regex-extract-columns.md](regex-extract-columns.md), [multi-line-entries.md](multi-line-entries.md), [robust-parsing.md](robust-parsing.md)

## Goal

A user can teach zLog their own log format — paste sample lines, write a
named-group regex, see it parse live — and every filter, color, and summary that
works on logcat then works on their log. zLog stops being Android-shaped.

**This is the primary plan for custom formats, and it stands alone.** It depends
on nothing unbuilt: the four built-in logcat patterns become entries in the same
list as the user's own, so there's one code path rather than two.

> **Ordering note (2026-08-04).** This was originally written as "phase 2 of
> two", after [custom-log-format-preset.md](custom-log-format-preset.md) added a
> single hard-coded pattern for one project's format. That ordering was wrong and
> has been reversed. The preset was never a technical prerequisite — it was meant
> to ship value while this was designed, but it turned out to be the plan that's
> *blocked* (it needs sample lines from the format's owner) while this one isn't.
> Worse, doing the preset first is largely wasted: once the editor exists, adding
> a format is a data entry in a built-in list, not parser work. Build this first.

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

## Decisions (resolved 2026-08-04)

**1. Format choice is per-tab.** One tab on logcat and another on a project log
is the normal case for a tabbed viewer, and a global setting breaks exactly
there. `core/tabstate.py` already persists per-tab `query`/`level`/`package`, so
this is an additive `format: str = ""` field on `TabState` (`""` = auto/try-all,
which is also what every existing stored tab decodes to — `tabs_from_json`
coerces defensively, so old settings files restore unchanged).

Consequence for the plumbing: the format list must reach whichever reader that
tab owns, at start. Pass it in — don't let a running reader call back for "the
current format", which would break the worker-thread rule.

**2. Auto-detect on open, and name the winner in the status bar.** Try each
format against the first N lines, score by how many parse, pick the best. Then
say which one was chosen — "Loaded 12,431 lines · format: MyProject". Silent
auto-detect is the worst option: a wrong pick shows mis-parsed fields with no
clue why, which is harder to diagnose than no parsing at all. Naming the choice
makes a wrong pick visible *and* is how a user discovers the feature exists.

Ties and no-match both fall back to today's behaviour (try all built-ins, raw
line if nothing matches). Detection reads only the first N lines, never the
whole file — this runs on every open, including the 100k-line ones.

**3. Slow-regex protection lives in the preview, not at runtime.** Time the
pattern against the sample lines plus a synthetic worst-case (a long line that
*nearly* matches — that's what triggers backtracking, not a line that matches
cleanly) and warn on a blowup. This catches the problem at the one moment the
user can still fix it, and adds nothing to the per-line hot path.

Explicitly **not** doing a runtime watchdog: it means either a thread/process
per match or swapping in the `regex` module for its timeout support, and that's
real complexity on a path that runs millions of times. Revisit only if a
pathological pattern actually bites someone.

## Scope

- **In:** a `LogFormat` value type (name, regex, level aliases, timestamp hint); a
  pure matcher that tries an ordered list of formats; persistence; a manager
  dialog with a live preview against pasted sample lines; **per-tab** format
  choice (decision 1); **auto-detect on open with the winner named in the status
  bar** (decision 2); **preview-time timing of the user's pattern** (decision 3);
  the built-ins exposed as read-only entries.
- **Out (non-goals):** multi-line entries ([multi-line-entries.md](multi-line-entries.md)),
  a runtime watchdog for slow regexes (decision 3 — preview-time only), a
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
| `src/zlog/core/logformat.py` (new) | core | `LogFormat`; `compile_formats(list[LogFormat])` skipping invalid regexes (like `core/extract.py` does) and reporting which failed; `apply_aliases(level, aliases)`; `formats_to_json`/`formats_from_json` for persistence (mirror `core/theme_io.py` and `core/tabstate.py`, which already solve exactly this). Plus `detect_format(sample_lines, formats) -> LogFormat \| None` for decision 2 — score each format by how many sample lines it parses, return the winner or `None` on a tie/no-match. Pure, fully unit-tested. |
| `src/zlog/core/parser.py` | core | `parse_line(line, formats=None)` — `None` keeps today's built-in behaviour, so **all five existing call sites keep working unchanged** (`adb/reader.py:133`, `cli.py:61`, `core/session.py:35` and `:47`, `ui/file_follower.py:147`). The built-in logcat patterns get restated as `LogFormat(builtin=True)` entries so there's one representation, not two. |
| `src/zlog/core/settings.py` | core | `"log_formats": []` in `DEFAULTS` — user formats only; built-ins are code, not settings. **No global `active_format`** — per decision 1 the choice is per-tab, and a global key would immediately compete with it as a second source of truth. |
| `src/zlog/core/tabstate.py` | core | `TabState` gains `format: str = ""` (`""` = auto-detect/try-all). Serialize it in `tabs_to_json`, coerce it defensively in `tabs_from_json` like every other field, so a settings file written by the current version restores unchanged. `restorable` is unaffected — a format alone isn't worth restoring a tab for. |
| `src/zlog/ui/log_format_dialog.py` (new) | ui | The manager: list of formats, add/edit/remove/reorder, and — the part that makes this usable — a **live preview**: a sample-lines box on top, a parsed-fields table below, updating as the regex is typed, with invalid-regex feedback inline. Show the **mapped** level (post-alias), not the captured raw token, so a broken alias map is visible while it's being written. Per decision 3, the preview also **times** the pattern against the samples plus a synthetic near-miss line and warns on a blowup. Without this preview the feature is unusable by anyone who doesn't already debug regexes for fun. |
| `src/zlog/ui/main_window.py` | ui | A menu action to open the dialog; on apply, persist and re-parse. Per the rule in [main-window-drift.md](main-window-drift.md), keep this to construction + signal wiring — any real logic goes in the dialog module or `core/`. |
| the readers (`adb/reader.py`, `ui/file_follower.py`, `core/session.py`) | ui/core | Accept the tab's compiled format list at construction and pass it to `parse_line`. **Hand it in at start; never let a running reader fetch "the current format"** — that would be a worker thread reading UI-owned state, which the architecture rules forbid. A format change applies to subsequent starts plus the explicit re-parse below. |
| `src/zlog/ui/main_window.py` | ui | On file open: read the first N lines, call `detect_format(...)`, apply the winner to that tab, and name it in the existing "Loaded N lines…" status message (decision 2). Sits next to the `all_unparsed` note added by [unparsed-level-hides-log.md](unparsed-level-hides-log.md) — same message, same moment. |
| `tests/test_logformat.py` (new) | — | Ordering (first match wins); invalid regex skipped, not crashing; aliases applied; unknown level → `""`; round-trip through JSON; a user format that shadows a built-in. |

### As actually implemented (2026-08-04) — deviations from the Design table above

- **Re-parsing already-loaded rows doesn't cache raw lines.** Rather than
  giving `LogEntry`/`LogTableModel` a parallel raw-line store (real, ongoing
  memory cost for every entry, forever, to support an edit-time-only
  feature), a format-dialog Apply on a tab that's a loaded file just calls
  `_load_log_file(sess.file_path)` again — a loaded file's tab *is* exactly
  its path's content, so re-reading it re-parses with the edited formats for
  free. `LogSession.file_path` already existed for Open Recent/tab-restore.
  A live-capture tab has nothing to reload from; its format takes effect
  from the next Start, as the Design table already said. See
  `MainWindow._reparse_active_tab_if_loaded`.
- **The status-bar format note only fires for a user-defined winner**, not a
  built-in one. Literally following decision 2 would announce "Format:
  threadtime" on every single ordinary logcat open, forever — pure noise for
  the overwhelmingly common case, and it doesn't serve decision 2's own
  stated reason ("how a user discovers the feature exists"), which only
  applies once a user format is actually in play. See `_format_note`.
- **The preview's timing probe needed a real safety fix, found by actually
  running it.** The first version used a fixed generic near-miss (400 `x`s).
  Two problems, both found by testing against `(a+)+$` rather than assuming:
  (1) a generic filler doesn't trigger backtracking at all for a pattern
  keyed to a specific character — `_build_probe` now seeds the repeat from a
  literal character in the pattern itself (skipping `\d`/`\w`-style escape
  letters), falling back to `x` only when the pattern has no literal to
  seed from; (2) 400 repetitions of the seed is *catastrophically* too long
  — `(a+)+$` against it doesn't finish in any practical time (Python's `re`
  has no way to interrupt a running match, so this would have frozen the
  whole UI on a single keystroke, the exact failure the check exists to
  prevent). Measured the real growth curve
  (`n=18: 8ms, 20: 26ms, 22: 113ms, 24: 465ms, 26: 1.8s, 28: 8.5s`) and set
  `_PROBE_LENGTH = 20` (bounded, ~27ms worst-case observed) with the warning
  threshold at 10ms (a normal pattern measured ~0.02ms against the same
  probe — over 1000x separation, comfortable margin either direction).
- **No format picker in the toolbar/device bar.** Per the plan's own open
  question below, left undecided and therefore not built — a tab's format is
  resolved automatically (remembered choice, or auto-detect) with no manual
  override UI in v1. To change a tab's format, edit or add the format in the
  dialog (which re-parses the active loaded tab) or open a fresh tab.
- **Menu location:** View → "Log &Formats…", next to "Extract Fields…" and
  "Highlight Rules…" (`ui/menus.py`) — the plan didn't specify a location.

**Re-parsing already-loaded rows** (original design, **not** what shipped —
see the deviation note above for what actually did). Changing the format must
update what's on screen, or the preview lies. The originally-planned approach
was to keep each entry's raw line and re-run the parse over the master list,
then `beginResetModel`/`endResetModel` once. What shipped instead reloads from
`sess.file_path` — same visible effect, no raw-line storage added to
`LogEntry`/`LogTableModel`.

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
  with no obvious cause. Python's `re` has no timeout, and per decision 3 we are
  **not** building a runtime watchdog — the defence is the preview timing, which
  only helps if the synthetic test line is a **near-miss** (long, matches most of
  the pattern, fails at the end). A line that matches cleanly runs fast and proves
  nothing. Get that sample right or the guard is theatre.
- **Auto-detect must not read the whole file.** It runs on every open, including
  the 100k-line ones that already have a progress dialog
  ([large-file-progress.md](large-file-progress.md)). Sample the first N lines
  only, and make sure detection happens *before* the bulk parse, not as a second
  pass over everything.
- **Auto-detect picking wrong is the failure users will report.** Naming the
  chosen format in the status bar is what makes it diagnosable rather than
  baffling — treat that message as part of the feature, not decoration.
- **Per-tab format must survive the tab-restore path.** `tabs_from_json` drops
  malformed entries silently by design; a new field is the classic thing to get
  wrong there. Test an old-format settings file (no `format` key) restores to
  `""` rather than dropping the tab.
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

- [x] With zero user formats configured, every existing parser test passes
      unchanged. `test_formats_none_is_byte_identical_to_default` pins this
      directly; the full suite (below) confirms no other test regressed.
- [x] Define a format for a real non-logcat file: preview shows correct
      fields (verified interactively via a headless script — a custom
      pattern's sample lines rendered with correct time/level/tag/message,
      including the mapped level shown, not the raw token); apply → the open
      log re-parses (`test_dialog_apply_persists_and_reparses_the_active_tab`);
      the level actually populated and the gate actually filters by it
      (`test_the_level_gate_actually_works_on_a_detected_custom_format`) —
      that's what drives level colors/dropdown/Tag Summary, so the mechanism
      is proven even though a running GUI's colors/dropdown widget weren't
      separately click-tested.
- [x] Invalid regex: `_update_preview` catches `re.error` and reports it
      inline without raising (code path shared with the already-tested
      `compile_formats` skip-invalid behavior); not separately driven through
      a live `LogFormatDialog` instance.
- [x] A deliberately greedy user pattern does **not** break logcat parsing —
      `test_builtins_tried_first_survive_a_greedy_user_format`.
- [x] Formats survive a restart (JSON round-trip) including a backslash-heavy
      pattern — `test_formats_json_round_trip_with_nasty_pattern`,
      `test_settings_round_trip_of_log_formats`.
- [x] **Per-tab (decision 1):** `test_two_tabs_each_keep_their_own_format_concurrently`
      — one tab on logcat, another on a custom format, both correct at once,
      switching back and forth disturbs neither.
- [x] **Tab restore:** `test_settings_file_without_format_key_defaults_to_auto`
      — a dict with no `"format"` key restores the tab with `format=""`, not
      dropped.
- [x] **Auto-detect (decision 2):** custom-format file picks the custom format
      (`test_open_detects_a_configured_custom_format`); a real logcat file
      picks threadtime but doesn't announce it
      (`test_no_user_formats_behaves_as_before`, refined — see the deviation
      note above); no confident match falls back to built-ins only, no crash
      (`test_no_confident_match_falls_back_to_builtins_only`).
- [x] **Auto-detect cost:** measured directly against a real 150,000-line
      (6.3MB) file — sampling the first `DETECT_SAMPLE_LINES` (200) lines via
      `itertools.islice` took 6.35ms, independent of file size (it never
      reads past line 200).
- [x] **Preview timing (decision 3):** measured directly — `(a+)+$` against
      the pattern-aware probe took ~27ms at `_PROBE_LENGTH=20` vs. ~0.02ms for
      an ordinary pattern (`test_time_pattern_catastrophic_pattern_is_much_slower_than_normal`);
      the dialog smoke-check confirmed the warning fires for the catastrophic
      case and stays silent for a normal, cleanly-matching pattern. This
      measurement is also what caught and fixed a real bug — see the
      deviation note above.
- [ ] A pathological regex against a **real large file** (not the preview):
      **not tested, deliberately.** Per decision 3 there is no runtime
      watchdog, and Python's `re` has no way to interrupt a running match —
      applying a genuinely catastrophic pattern to a real capture would hang
      that load with no way to cancel except killing the process. This is the
      accepted, disclosed cost of the decision, not a bug to fix here; actually
      triggering it would just hang a verification run for no new information.
- [x] `uv run pytest -q` in one process (CI's command) — 817 passed, exit 0
      (the post-`[100%]` line is the pre-existing, already-explained Windows
      shutdown artifact — see ci-windows-job.md).
- [x] `uv run ruff check .` / `ruff format --check .` clean across the repo.
- [x] Headless app smoke test (`run-zlog` driver): window renders normally,
      no crash, with the new "Log &Formats…" menu action wired in.

## Open questions

- **Should this absorb `regex-extract-columns`' patterns?** They're solving
  adjacent problems with two mechanisms. Leaning no for now — unifying them is
  worthwhile but is a third plan, and doing it here doubles the blast radius.
- **How many lines should auto-detect sample?** Enough to beat a file that opens
  with a banner or a blank run before real content starts. A few hundred is
  likely right; confirm against a real file rather than guessing.
- **What does the format picker look like** — a combo in the device bar, or only
  in the dialog? The bar is more discoverable but the header is already crowded
  (see `ui-toolbar-width-and-tab-labels.md`, which fixed a hard width floor).
