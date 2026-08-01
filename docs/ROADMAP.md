# zLog — Long-Term Development Roadmap

A strategic view of where zLog is going and how its parts are prioritized. It sits
above the per-feature plans in `docs/plans/` (which stay the unit of execution) and is
revisited each release. Dates are cadence, not commitments.

## Where we are (snapshot, 2026-08-01)

- **v1.1.0 shipped**; **v1.1.1** is prepared (see
  [release-1.1.1.md](plans/release-1.1.1.md)) — a patch covering a real shipped bug
  (a missing-adb Windows machine couldn't reach **This PC**, fixed in
  [usable-without-adb.md](plans/usable-without-adb.md)) plus the offer-to-fetch-adb
  flow ([bundle-adb.md](plans/bundle-adb.md)) and UI polish.
- **~760 tests** across `core`, `ui`, `adb`, and `winlog`; CI runs them headless
  (offscreen Qt) on Linux.
- **The feature backlog is empty** — `docs/plans/backlog.md` tracks new raw ideas,
  but every previously-listed candidate has shipped or has its own plan. zLog covers
  five log sources (Android `adb logcat`, Windows debug output, Windows Event Log, a
  launched app, a followed file), a single unified query bar, saved filters, tabs,
  export/session bundles, and a themeable, virtualized log view — a mature,
  feature-complete tool for what it set out to do.
- **The current phase is quality and delivery, not features**: platform CI
  coverage, line-ending hygiene, doc accuracy (this file included, until this
  update), and keeping `main_window.py` from regrowing past its last refactor. See
  "Near-term: the tech-debt program" below — that register, not a version-phase
  list, is the accurate picture of what's next.
- **One bigger bet stayed a Draft and was abandoned**: [etw-tracing.md](plans/etw-tracing.md)
  (ETW real-time provider tracing) — too risky for the payoff at the time; revisit
  if a concrete need shows up.

## Guiding principles (do not regress these)

1. **Plan-first.** Every feature/notable change gets a plan in `docs/plans/` first.
2. **Layered & Qt-free `core`.** One-way deps `ui → {adb, winlog} → core`; logic
   that can be pure goes in `core` and gets unit tests. Workers reach the UI only
   via signals. See `docs/ARCHITECTURE.md`.
3. **Virtualized & responsive.** The model stays virtualized; nothing may make the
   common path O(all rows). Reading happens off the UI thread.
4. **Cross-platform, Windows-first.** Ship a Windows exe via cx_Freeze; keep the
   code portable — and, per [ci-windows-job.md](plans/ci-windows-job.md), actually
   test the Windows-only code paths, not just build them.
5. **Every feature lands green.** Tests + ruff + a headless check before it's Done.

## Near-term: the tech-debt program

Unlike the shipped feature phases below, this is the live work register — each row
is its own plan, ordered by the dependency chain the plans themselves specify:

| Plan | What it fixes |
|---|---|
| [gitattributes-line-endings.md](plans/gitattributes-line-endings.md) | No `.gitattributes` meant every file "changed" on the other OS's checkout, hiding real diffs. Prerequisite for the Windows CI job. |
| [ci-windows-job.md](plans/ci-windows-job.md) | `ci.yml` only runs `ubuntu-latest` — 750+ lines of Windows-only code (`winlog/`, `core/dbwin.py`, `core/winevent.py`) have never executed in CI. |
| [ci-shuffled-order.md](plans/ci-shuffled-order.md) | A shuffled-order CI job to catch order-dependent tests deliberately, rather than by accident (as the follow-scroll flake was). Sequenced after the Windows job. |
| [architecture-doc-refresh.md](plans/architecture-doc-refresh.md) | This file and `docs/ARCHITECTURE.md` had drifted — zero mentions of `winlog`/`dbwin`/`file_follower`/`capture_controller`/`tabstate`, which carry roughly half of what zLog now does. |
| [main-window-drift.md](plans/main-window-drift.md) | `main_window.py` regrew from 3,050 to 3,581 lines in the ~7 features since its last split. A written convention (new UI work gets its own `ui/` module) plus two extractions, so it holds this time. |
| [split-settings-tests.md](plans/split-settings-tests.md) | `test_main_window_settings.py` is 1,277 lines covering four unrelated subjects — the slowest file, and where both known test flakes surfaced. |

## Cross-cutting tracks (continuous, every version)

- **Testing** — keep `core`/`ui`/`adb`/`winlog` coverage growing with each feature;
  CI gates merges. Windows and shuffled-order coverage are landing now (see above).
- **Docs** — keep `docs/GUIDE.md`, `CLAUDE.md`, and `docs/ARCHITECTURE.md` in step
  with the code. They've drifted before (this file included) — doc-sync is part of
  "Done" for any change that adds a module or a rule.
- **Release & distribution** — the `v*` workflow is in place; consider code signing
  and an installer (MSI/Inno Setup) as adoption grows; keep `uv.lock`/Python floor
  current.
- **Health** — periodic tech-debt passes (the register above); watch the
  deprecated-API surface as PySide6 evolves.

## Release / quality gate (every version)

A version ships only when: all tests pass, ruff is clean, the GUIDE reflects new
features, the CHANGELOG is updated, and the tagged build produces a working exe —
per [release-workflow.md](plans/release-workflow.md) and the `release-zlog` skill.

## Key risks & watch-items

- **Windows code paths were untested in CI until the tech-debt program above** —
  the exact class of bug this already caused twice (`file_key`'s `st_ctime`
  meaning, and the `refresh_devices` early-return that shipped in 1.1.0). Landing
  [ci-windows-job.md](plans/ci-windows-job.md) is the fix, not vigilance.
- **`main_window.py` regrowth** — a one-time carve-up erodes; the convention in
  [main-window-drift.md](plans/main-window-drift.md) is meant to be the durable
  fix. Watch whether it actually holds over the next several features.
- **Performance regressions** as filters/decorations grow — profile against a
  large capture before each release; keep per-row work O(1).
- **Parser brittleness** on non-standard logcat formats remains the single
  biggest correctness risk for the Android source specifically.
- **Feature sprawl vs. focus** — the backlog is empty by design; a new feature
  idea gets a plan and a deliberate decision, not a reflexive yes.
