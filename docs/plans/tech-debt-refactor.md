# Plan: Tech debt remediation (Q3 2026)

- **Status:** Draft
- **Owner:** Vũ
- **Created:** 2026-07-07
- **Related:** refactor-main-window.md (prior pass this one follows up on)

## Goal

Pay down the debt that's accumulated since the last refactor — mainly that `ui/`
has zero automated test coverage and `main_window.py` has grown back past its
pre-refactor size — without slowing down feature work, by doing it in three
small, independently-approvable phases.

## Findings (scored)

Priority = (Impact + Risk) × (6 − Effort); all 1–5, Effort inverted (1 = easy).

| # | Item | Impact | Risk | Effort | Priority |
|---|---|---|---|---|---|
| 1 | `ui/` has no automated tests — `main_window.py` (730 lines, 48 methods) is only checked by manual smoke screenshots | 5 | 5 | 3 | 30 |
| 2 | CI never imports/exercises `zlog.ui` (offscreen Qt) or runs on Windows — only `core/` is covered by `pytest` | 3 | 4 | 2 | 28 |
| 3 | Duplicated adb-call error handling — the same try/except (`FileNotFoundError` → "adb not found", generic `Exception` → message) appears 3× in `refresh_devices`, `load_packages`, `apply_package_filter` | 2 | 2 | 1 | 20 |
| 4 | No dependency-update automation (no Dependabot/Renovate for `uv.lock` or Actions versions) | 2 | 3 | 1 | 25 |
| 5 | `main_window.py` is a growing God object — already 48% of app code; a controller extraction was explicitly deferred in `refactor-main-window.md` and the file has since regrown from 662 → 730 lines | 4 | 3 | 4 | 14 |
| 6 | `self._search_error_color = "#ffd7d7"` is a hard-coded fallback literal duplicating `LIGHT.search_error`, a narrow exception to the "colors live in `ui/theme.py`" rule | 1 | 1 | 1 | 10 |

### Why each matters

- **#1/#2 (test + CI gap):** every UI regression today is caught only by eyes on
  a screenshot. This is not hypothetical — `refactor-main-window.md` records a
  real incident ("silent truncation of `main_window.py` during edits, happened
  during remember-device"). The fix is cheaper than it looks:
  `.claude/skills/run-zlog/scripts/driver.py` already proves `MainWindow` runs
  fine under `QT_QPA_PLATFORM=offscreen`; that same technique just needs to move
  into `tests/` and CI instead of living only in a manual skill.
- **#3:** pure duplication — three copies of the same error-mapping means a
  fourth adb call is likely to paste-and-diverge instead of reusing it.
- **#4:** a single pinned dependency (`PySide6>=6.6`) is low risk today, but
  nothing currently notices when it or `uv`/Actions versions go stale.
- **#5:** the team already flagged this as a deferred, not a rejected, idea
  ("Not extracting a `DeviceController`/`FilterController` — bigger, riskier —
  a separate later plan if we want it"). Growth since then is the signal to
  revisit it, not new information to discover.
- **#6:** cosmetic — the value is always overwritten by `apply_theme` before
  paint, so this is a rule nit, not a bug.

## Scope

- **In:** the three phases below.
- **Out (non-goals):** no new user-facing feature; no version bump
  (release-only policy); Phase 3's actual extraction is *out* of this plan —
  this plan only decides it's worth doing and hands it to its own
  `docs/plans/<slug>.md` before any code changes, per the plan-first rule.

## Phased remediation

**Phase 1 — quick wins (do alongside any other work, no separate approval needed beyond this plan):**
- Extract a shared `_run_adb_call(fn, *, not_found_msg)` (or similar) helper in
  `main_window.py` and point `refresh_devices` / `load_packages` /
  `apply_package_filter` at it. Behavior-preserving.
- Drop the redundant `"#ffd7d7"` literal — initialize `_search_error_color` from
  `LIGHT.search_error` (still overwritten by `apply_theme` right after).
- Add `.github/dependabot.yml` covering the `uv`/pip ecosystem and
  `github-actions`.

**Phase 2 — close the UI test gap:**
- Add an offscreen Qt smoke test (`QT_QPA_PLATFORM=offscreen`, same trick as
  `run-zlog`'s driver) that constructs `MainWindow` and exercises, headlessly:
  the settings round-trip (`_settings_specs()` assert already guards key drift,
  but nothing calls it in CI today), `_track_new_pids`, and
  `_selected_entries`/`_filtered_entries` proxy-mapping logic.
- Add a CI step running this alongside the existing `core/` suite. (A full
  Windows test runner is a nice-to-have, not required — offscreen Qt runs fine
  on `ubuntu-latest`, same as the release build's Windows-only step is separate.)

**Phase 3 — revisit the deferred controller extraction:**
- Once Phase 2 gives a safety net, write a fresh `docs/plans/<slug>.md` (e.g.
  `device-filter-controllers.md`) scoping a `DeviceController`/`FilterController`
  extraction from `main_window.py`, following the same behavior-preserving
  approach as `refactor-main-window.md`. Get it approved before touching code.

## Architecture touch points

- **Threading:** none in Phases 1–2. Phase 3 must preserve "workers reach the UI
  only via signals" if any state moves into a controller object.
- **Dependency direction:** unchanged (`ui → adb → core`); Phase 1's helper and
  Phase 3's controllers stay inside `ui/`.
- **Colors rule:** Phase 1 item 2 brings `main_window.py` fully into compliance.

## Risks & regressions to check

- Phase 1: re-run the 3 refactored flows manually (no device, adb missing, adb
  timeout) to confirm identical status-bar messages.
- Phase 2: offscreen tests must not depend on a real device or `adb` binary —
  fake data only, matching how `_populate_devices` already supports the
  run-zlog driver's fake devices.
- Phase 3: same risks called out in `refactor-main-window.md` (silent
  truncation, settings round-trip, restore ordering) — Phase 2's tests are what
  make this safe to attempt.

## Verification

- [ ] `uv run pytest` (Phase 2 adds the offscreen suite here)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual re-check of the three adb-call flows after Phase 1's extraction
- [ ] CI green with the new job/step from Phase 2
- [ ] Phase 3 gated on its own approved plan before any code changes

## Open questions

- Phase 2: `pytest-qt` (adds a dev dependency) vs. a hand-rolled
  `QApplication` fixture (zero new deps, more boilerplate) — leaning hand-rolled
  since the app has exactly one window class today.
- Phase 3: scope as one `DeviceController` + one `FilterController`, or fold
  device/package/search into a single `FilterController`? Decide in that plan,
  not this one.
