# Plan: Split test_main_window_settings.py

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-01
- **Related:** [fix-follow-scroll-flake.md](fix-follow-scroll-flake.md), [ci-shuffled-order.md](ci-shuffled-order.md), [main-window-drift.md](main-window-drift.md)

## Goal

The settings test file stops being the place tests go when they don't obviously
belong anywhere else, so a failure name tells you what broke.

## Why

`tests/test_main_window_settings.py` is **1,277 lines / 79 tests** — the largest
test file in the repo by a wide margin — and it covers settings persistence *and*
follow-scroll *and* density modes *and* word-wrap. Those share a fixture, not a
subject.

Two concrete costs:

- **It's the slowest file (~40 s)**, and there's no way to run just the part
  relevant to your change. Given local runs here are already chunked to fit a
  timeout, a 40-second monolith is the chunk that hurts.
- **It's where both flakes surfaced.** The follow-scroll flake
  ([fix-follow-scroll-flake.md](fix-follow-scroll-flake.md)) lived here, and
  diagnosing it meant reasoning about which of 79 tests ran before it. A file
  that mixes subjects makes ordering effects harder to see and easier to blame on
  the wrong thing.

This is genuine debt but not urgent: the tests **work**, they catch regressions,
and nothing is silently unverified. It's a maintainability tax, so it's last.

## Scope

- **In:** split into subject-named files; move the shared setup into a fixture
  they can all use; keep every assertion exactly as-is.
- **Out (non-goals):** rewriting or "improving" any test's assertions (that's how
  a split quietly loses coverage), deleting anything, splitting other large files,
  and changing production code.

## Design

A pure move, by subject. If a test's name doesn't say which new file it belongs
in, that's a sign the test itself is unclear — note it, don't fix it here.

| File | Contents |
|---|---|
| `tests/test_main_window_settings.py` (stays) | Settings **persistence** only: save/restore round-trips, defaults, `_settings_specs` coverage, the Settings dialog wiring. This is the file's original purpose. |
| `tests/test_follow_scroll.py` (new) | Follow/auto-scroll behaviour, including the anti-yank `value == 0` assertions and the three near-bottom checks. Grouping them makes the two-pass-plus-deferred-re-pin behaviour readable in one place, which is exactly what was hard during the flake hunt. |
| `tests/test_view_modes.py` (new) | Density modes, word-wrap, gutter, font zoom — the presentation toggles. |
| `tests/conftest.py` | Whatever setup the three now share moves here as a fixture, rather than being copy-pasted into each new file. |

Order the work as: create the new files by moving tests verbatim → confirm the
same total count → then delete from the original. Never both at once in one
commit that's hard to verify.

## Architecture touch points

- **Threading / model / dependency direction:** none. Test-only.

## Risks & regressions to check

- **Silently dropping tests is the whole risk.** Count before and after and make
  the numbers match exactly (79 in, 79 out). A split that loses four tests looks
  identical to a successful one in a green CI run.
- **Shared module-level state** (a `QSettings` scope, a temp dir, a monkeypatched
  platform) may be established by an early test in the current file and relied on
  implicitly by a later one. Once they're in separate files that ordering is gone —
  which is *better*, but it may surface a latent dependency as a new failure.
  Treat any such failure as a real finding about the test, not as a reason to
  merge the files back.
- **The `qapp` fixture is session-scoped**; confirm splitting across files doesn't
  change how many `MainWindow` instances live at once (a leak shows up as slow
  tests or an offscreen crash).
- **Don't tidy while moving.** Verbatim move first; any improvement is a separate
  commit so a bisect can distinguish them.

## Verification

- [x] `pytest --collect-only -q` identical before and after: **80** tests across
      the three files both before (all in one file) and after (73 + 3 + 4), and
      **765** repo-wide, unchanged from the pre-split baseline.
- [x] Each new file passes **alone**: `test_follow_scroll.py` (3 tests, ~3.4s)
      and `test_view_modes.py` (4 tests, ~2.8s) both green standalone.
- [x] `uv run pytest -q` in **one process** (CI's command) — green: 765 passed,
      exit 0 (the `Windows fatal exception: access violation` line after
      `[100%]` is the pre-existing, already-root-caused shutdown artifact
      `conftest.py`'s `pytest_sessionfinish` hook exists to paper over — see
      [ci-windows-job.md](ci-windows-job.md); exit code is still correct).
- [x] Run 3× (shuffled, `-p randomly`, since
      [ci-shuffled-order.md](ci-shuffled-order.md) has since landed): all three
      runs of the touched files (80 tests) green, no failures in any order.
- [x] Per-file timings recorded (local Windows dev machine, standalone):
      `test_main_window_settings.py` (73 tests) ~120s, `test_follow_scroll.py`
      (3 tests) ~3.4s, `test_view_modes.py` (4 tests) ~2.8s. The absolute
      numbers are higher than the plan's original CI-based "~40s" estimate for
      the *whole* file (this machine's per-test `MainWindow` construction
      overhead is higher than CI's offscreen Linux runner), but the relative
      win the split was for is real: touching follow-scroll or zoom/font logic
      no longer requires waiting on the other 73 tests.
- [x] `uv run ruff check .` / `ruff format --check .` clean on all three files.

Note on scope: the plan named three destination files, but the tests actually
in this file span far more subjects than "persistence" alone (query bar,
presets, watch, tabs, sessions, autosave, goto, bookmarks, adb path, …). Per
this plan's own non-goal ("splitting other large files" is out of scope), only
the two subjects it explicitly named — follow-scroll and the zoom/font
presentation toggles — were extracted; everything else stays. The remaining
`test_main_window_settings.py` is smaller (73 tests) but still a grab bag; a
further split, if wanted, is new scope for a new plan.

Note on the shared fixture: the plan called for moving the shared `window`
fixture into `conftest.py`. Six other `test_main_window_*.py` files
(`test_main_window_tabs.py`, `_adb.py`, `_evtlog.py`, `_plugins.py`,
`_presets.py`, `_dbwin.py`) already each define the identical fixture locally
rather than sharing one from `conftest.py` — that's the codebase's actual,
established convention for this fixture. Matching it (defining `window`
locally in the two new files too) was judged safer and more consistent than
introducing the first shared instance of a fixture six other files
deliberately duplicate.

## Open questions

- **Three files or two?** Density/wrap/gutter could stay with settings, since
  they're settings-driven. Leaning three: they test *rendering* behaviour, not
  persistence, and rendering is what breaks.
- Do other files deserve the same treatment? `test_log_model.py` is next largest
  but is genuinely about one subject. Leave it.
