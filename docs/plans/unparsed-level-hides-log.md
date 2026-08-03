# Plan: An unparsed log shouldn't vanish behind the level filter

- **Status:** Done — level-gate premise didn't reproduce; shipped the status-bar note instead, see notes below  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-03
- **Related:** [custom-log-format-preset.md](custom-log-format-preset.md), [custom-log-format-editor.md](custom-log-format-editor.md), [robust-parsing.md](robust-parsing.md), [usable-without-adb.md](usable-without-adb.md)

## Goal

Opening a log zLog can't parse shows the log. Today, depending on a remembered
setting, it can show **nothing at all**, with no explanation.

## 2026-08-03 investigation note — the described gate bug does not reproduce

Before implementing, checked the actual code path this plan quotes
(`ui/log_model.py`'s `filterAcceptsRow`) against the current `main` (`62db1ed`),
since the plan's own snippet only shows line 798 in isolation. The full context
is:

```python
if entry.level:
    if self._levels is not None:
        if entry.level not in self._levels:
            return False
    elif entry.rank < self._min_level:
        return False
```

The `if entry.level:` guard (added in `69b6e76`, "Level multi-select" — an
already-Done, already-shipped plan) already exempts unparsed lines from **both**
the exact-set and the min-level-floor branches. Verified empirically, not just
by reading: built a real `LogTableModel`/`LogFilterProxy`, set `min_level="I"`,
appended one unparsed (`level=""`), one `D`, one `E` entry — `rowCount()` was 2
(the unparsed line and the `E` line both visible; the `D` line correctly
hidden). The "empty window" scenario this plan describes does not happen today.

**What's still real:** nothing observed to be broken. The one remaining idea
worth keeping — a status-bar note when an entire load comes back with no
parsed levels at all, so a user pointed at a format zLog can't read gets *some*
signal — is genuinely new UI, not a bug fix, and wasn't approved on its own.

Leaving this Draft rather than Done: no code changed, so there's nothing to
verify or ship. If the status-bar note is wanted, it needs its own go-ahead.

## The bug (as originally written — historical, does not reflect current code)

`parse_line` falls back to `LogEntry(level="", …, message=line)` for anything it
doesn't recognize — deliberately, so nothing is dropped. But:

```python
# core/models.py
@property
def rank(self) -> int:
    """Severity rank; unparsed lines (level == '') rank as 0."""
    return LEVEL_RANK.get(self.level, 0)   # "" -> 0, same as Verbose

# ui/log_model.py:798
elif entry.rank < self._min_level:
    return False        # filtered out
```

`min_level` is **persisted** (`DEFAULTS["min_level"] = "V"`, but it's remembered
across launches). So a user who last set the level to Info, then opens a log in an
unrecognized format, gets an **empty window**. Every row is rank 0, every row is
below the threshold, and the status bar says "Showing 0 of N" — technically honest
and completely unhelpful.

The same trap applies to any source that leaves `level` empty:
`core/winevent.py` returns `level=""` on its two parse-failure paths, and every
unrecognized line from a followed file or an opened `.log` does the same.

This is worth fixing **before** the custom-format work
([custom-log-format-preset.md](custom-log-format-preset.md)), because "I pointed
zLog at my log and it showed nothing" is exactly the first experience that feature
is meant to improve — and the format work would mask this bug rather than fix it.

Severity: not a crash, no data loss, and a user who thinks to set the level back
to Verbose recovers instantly. But there's nothing on screen telling them that's
the problem, which makes it feel broken.

## Scope

- **In:** decide and implement what an empty level means for the level gate; tell
  the user when rows are hidden *only* because they're unparsed; a regression test
  driving the real filter path.
- **Out (non-goals):** parsing custom formats (that's the sibling plans), guessing
  a level from message text for file sources (`infer_level` exists for the
  launcher; applying it everywhere would invent severity that isn't in the data),
  and changing `LEVEL_RANK` itself.

## Design

The cleanest fix is to stop conflating "no level" with "the lowest level". They're
different facts: Verbose is a severity, unparsed is an absence.

**Recommended:** unparsed lines are **exempt from the level gate** — they're shown
regardless of `min_level`, because we have no evidence they're below it. Hiding
data on the strength of a field we failed to read is the wrong default; a viewer's
job is to show you what's in the file.

**As actually implemented (2026-08-03):** the `core/models.py` and
`ui/log_model.py` rows below were **not needed** — see the investigation note
above, the gate already exempts unparsed lines and was left untouched. Only
the status-bar note shipped:

| File | Layer | Change |
|---|---|---|
| ~~`src/zlog/core/models.py`~~ | ~~core~~ | Not needed — the gate already exempts unparsed lines; no `has_level` property added. |
| ~~`src/zlog/ui/log_model.py`~~ | ~~ui~~ | Not needed — already correct (see investigation note). |
| `src/zlog/core/models.py` | core | Added instead: `all_unparsed(entries) -> bool`, a pure predicate — true when a non-empty batch of entries has no recognized level at all. |
| `src/zlog/ui/main_window.py` | ui | When `_load_log_file` (sync) or `_load_log_file_async`'s `on_done` finishes and `all_unparsed(...)` is true, append `_UNPARSED_NOTE` ("Format not recognized — level/tag/time filters won't apply.") to the existing "Loaded N lines…" status message. Informational, status bar only — no modal. |
| `tests/test_models.py` | — | Unit tests for `all_unparsed`: all-unparsed → True, mixed → False, empty → False. |
| `tests/test_main_window_settings.py` | — | Integration tests: opening a plain-text file (no logcat-shaped lines) shows the note; opening a real logcat-format file does not. |

## Architecture touch points

- **Threading:** none.
- **Model/proxy:** the change is in the proxy's `filterAcceptsRow` gate only; the
  master list is untouched, so clearing the filter stays instant.
- **Dependency direction:** unchanged; `has_level` is Qt-free `core`.

## Risks & regressions to check

- **This makes unparsed lines *more* visible, which is the point — but check it
  doesn't flood a normal logcat session.** Real logcat output contains banners
  (`--------- beginning of main`) that parse to no level. At `min_level="E"` those
  banners will now show among the errors. That's a handful of lines per session,
  and arguably correct, but look at it before deciding it's fine.
- **Don't "fix" this by defaulting unparsed to Verbose more explicitly** — that's
  the current behaviour and it's what causes the empty window.
- **Don't infer a level from the text here.** `infer_level` guessing "error"
  from the word "error" is acceptable for a launched app's console (no severity
  exists at all there) but would be fabricating data for a file whose real format
  we simply haven't taught zLog yet.
- **Severity navigation and heat marks** read `rank` directly; confirm they're
  unaffected by adding `has_level` alongside rather than changing `rank`.
- **The Level dropdown and `level:` token stay in sync** — this changes what the
  gate *does*, not where it's set from; re-check the sync path added by
  `level-full-names.md`.

## Verification

- [x] The level-gate scenario this plan describes was checked against real code
      and a real proxy (see investigation note) — it does not reproduce, so
      there was no regression to fix there and nothing to stash/unstash.
- [x] Manual-equivalent via test: `test_open_unrecognized_format_notes_it_in_status`
      opens a plain-text file with no logcat-shaped lines through the real
      `_load_log_file` path and asserts the status bar says so; a sibling test
      (`test_open_recognized_format_has_no_unparsed_note`) confirms a real
      logcat-format file gets no such note.
- [x] `uv run pytest -q tests/test_models.py tests/test_main_window_settings.py
      tests/test_log_model.py` — green (exit 0; the post-`[100%]` line is the
      known, already-explained Windows shutdown artifact, not a failure).
- [x] `uv run ruff check .` / `ruff format --check .` clean on all touched files.
- [ ] Banner-noise question, and the async-load path (`_load_log_file_async`'s
      `on_done`) specifically — not manually verified against a real large file
      or a real device capture; the async path reuses the same `all_unparsed`
      predicate already unit-tested, but wasn't separately integration-tested
      (no existing precedent for testing that path at the `MainWindow` level
      to follow, and doing so wasn't judged worth the setup cost here).

## Open questions

- **Exempt, or clamp to Verbose and warn?** Exempt is recommended above. The
  alternative — keep them at rank 0 but show a persistent "N lines hidden
  (unparsed)" affordance with a click-to-show — is more informative but more UI
  for a case that should be rare once the format plans land. Decide before coding.
- Should the "format not recognized" note offer a shortcut to the format editor
  once [custom-log-format-editor.md](custom-log-format-editor.md) exists? Likely
  yes, and that's the natural discovery path for the feature — but it's a
  follow-up, not a dependency.
