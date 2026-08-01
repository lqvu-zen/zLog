# Plan: Split test_main_window_settings.py

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
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

- [ ] `pytest --collect-only -q | wc -l` identical before and after.
- [ ] Each new file passes **alone** (`pytest tests/test_follow_scroll.py`) — the
      point of the split is that this is now useful.
- [ ] `uv run pytest -q` in **one process** (CI's command) — green. Local runs
      here are chunked across processes and cannot prove the ordering
      independence this change specifically affects, so CI is the real gate.
- [ ] Run 3× to catch anything the reshuffle destabilized. If
      [ci-shuffled-order.md](ci-shuffled-order.md) has landed, run shuffled too.
- [ ] Per-file timings recorded, to confirm the "run just the relevant slice"
      benefit is real and not imagined.
- [ ] `uv run ruff check .` / `ruff format --check .` clean.

## Open questions

- **Three files or two?** Density/wrap/gutter could stay with settings, since
  they're settings-driven. Leaning three: they test *rendering* behaviour, not
  persistence, and rendering is what breaks.
- Do other files deserve the same treatment? `test_log_model.py` is next largest
  but is genuinely about one subject. Leave it.
