# zLog — Long-Term Development Roadmap

A strategic view of where zLog is going and how its parts are prioritized. It sits
above the per-feature plans in `docs/plans/` (which stay the unit of execution) and is
revisited each release. Dates are cadence, not commitments.

## Where we are (snapshot, 2026-07-08)

- **1.0.0 shipped**; the **1.1 cycle** has added a large batch of features
  (device picker, package/PID filter, regex + case + exclude search, highlight mode,
  match navigation, filter presets, relative-time column, bookmarks, jump-to-latest,
  showing-count, font zoom) on top of a **layered, tested** codebase.
- **109 tests** across `core`, `ui`, and `adb`; CI runs them headless (offscreen Qt).
- The **tech-debt program is complete** (UI/adb coverage, CI Qt job, adb-error dedupe,
  `DeviceController` extraction, doc sync, deprecation fixes).
- The app is a solid **single-device, single-stream logcat viewer**. The roadmap below
  is about making it *trustworthy at scale*, *faster to work in*, and *pleasant to read*.

## Guiding principles (do not regress these)

1. **Plan-first.** Every feature/notable change gets a plan in `docs/plans/` first.
2. **Layered & Qt-free `core`.** One-way deps `ui → adb → core`; logic that can be pure
   goes in `core` and gets unit tests. Workers reach the UI only via signals.
3. **Virtualized & responsive.** The model stays virtualized; nothing may make the
   common path O(all rows). Reading happens off the UI thread.
4. **Cross-platform, Windows-first.** Ship a Windows exe via cx_Freeze; keep the code
   portable.
5. **Every feature lands green.** Tests + ruff + a headless check before it's Done.

## How components are prioritized

Each component is scored on **User value**, **Effort**, and **Risk**, then bucketed:

- **P0 — Foundational:** correctness, performance, and capture reliability. If these are
  weak, nothing else matters. Do first.
- **P1 — High-leverage UX:** the daily-driver improvements most users will feel.
- **P2 — Power / delight:** valuable for heavy users but not blocking; do when P0/P1 are
  healthy.
- **P3 — Exploratory:** bigger bets that need their own design pass.

## Component pillars & priority

| Pillar | What it covers | Priority | Why |
|---|---|:--:|---|
| **Parsing & model correctness** | Non-threadtime formats, malformed lines, huge messages | **P0** | Trust: a viewer that mis-parses is worse than none. |
| **Performance at scale** | Ring-buffer cap, large-file open, millions of lines | **P0** | The core promise; must stay smooth on real captures. |
| **Capture & devices** | Custom `adb` args/buffers, clear buffer, pause/resume, auto-reconnect | **P0/P1** | Getting the *right* logs reliably is the primary job. |
| **Filtering & search** | Level multi-select, mute tag/PID, per-column filters, search history | **P1** | Where users spend their time; several drafts ready. |
| **Reading & navigation** | Monospace toggle, severity jumps, collapse repeats, stack-trace folding, minimap | **P1/P2** | Turns a wall of text into something scannable. |
| **Sessions & export** | Open-recent, CSV/JSON/HTML export, session bundles, autosave | **P1/P2** | Sharing and coming back to a capture. |
| **Analysis & insight** | Tag/level histograms, error-rate trend, diff two captures | **P2** | High value for debugging sessions; needs design. |
| **Appearance & UX polish** | More themes, per-level text color, density, status indicators | **P2** | Comfort and clarity; incremental. |
| **Extensibility** | Multiple device tabs, plugins/custom parsers, command palette | **P3** | Platform-level bets for after the fundamentals. |
| **Quality & delivery** | Tests, CI, docs, release automation, distribution | **P0 (ongoing)** | The rails everything else rides on. |

## Phased roadmap

Version cadence is the milestone. Each phase ends with a release (bump + CHANGELOG +
tag; the workflow builds/publishes the exe).

> **Status (2026-07-11):** every item below is **implemented and tested** (210
> passing tests) but **not yet released** — the shipped binary is still the July‑1
> 1.0.0 build. The immediate next step is to **cut a release** (bump, CHANGELOG,
> tag). The only roadmap item not built as originally framed is **multiple device
> *tabs*** are now implemented ([device-tabs.md](plans/device-tabs.md)); **New Window**
> ([new-window.md](plans/new-window.md)) remains as an alternative for separate windows.

### v1.1 — Finish the current cycle — **DONE (unreleased)**
Ship the in-flight search/filter polish, then cut the release.
- Build the three ready Drafts: **mute-tag**, **level multi-select**, **search history**.
- Optional quick win: **monospace toggle** (pairs with font zoom).
- Quick win: **UI review polish** — Message header alignment, bookmark/checkbox
  contrast (see [ui-review-polish.md](plans/ui-review-polish.md)).
- **Cut 1.1** (version bump, CHANGELOG, `v1.1.0` tag → auto-built exe).

### v1.2 — Capture & scale — **DONE (unreleased)**
Make zLog trustworthy on long, real-world captures.
- **Custom adb args**: buffer selection (main/system/crash/radio), tail count, format.
- **Clear device buffer** (`adb logcat -c`).
- **Pause/resume** stream (buffer while paused) without stopping adb.
- **Ring-buffer cap** — keep the last N lines to bound memory.
- **Auto-reconnect** on device drop/return.
- **Robust parsing** — handle `brief`/`time`/`tag` formats and odd lines gracefully.

### v1.3 — Sessions & export — **DONE (unreleased)**
Sharing and returning to captures.
- **Open-recent** menu; **reopen last session** on launch.
- **Export** to CSV/JSON/HTML; copy-as-Markdown; message-only copy.
- **Session bundles** — log + filters + bookmarks saved/reopened together.
- **Autosave / rotating capture** to disk while streaming.

### v1.4 — Reading & analysis — **DONE (unreleased)**
Turn volume into signal.
- **Collapse repeated lines** ("×N"); **stack-trace folding**.
- **Severity navigation** (jump to next error/warning); **scrollbar heat marks**.
- **Tag/level histogram** panel; **error-rate sparkline** in the status bar.
- Column reordering (persisted), remember splitter sizes, per-level text color.

### v2.0 — Platform bets — **DONE (unreleased)**
Bigger architectural moves, each with its own design.
- **Multiple device tabs** (concurrent streams).
- **Command palette** (Ctrl+K); **watch-pattern desktop notifications**.
- **Plugin hooks** — custom parsers/colorizers.
- **Diff two captures** side by side.

## Cross-cutting tracks (continuous, every version)

- **Testing** — keep `core`/`ui`/`adb` coverage growing with each feature; the CI Qt job
  gates merges. Add large-capture performance smoke tests as scale work lands.
- **Docs** — keep `docs/GUIDE.md`, `CLAUDE.md`, and `docs/ARCHITECTURE.md` in step with
  the code (they've drifted before; treat doc-sync as part of "Done").
- **Release & distribution** — the `v*` workflow is in place; consider code signing and
  an installer (MSI/Inno Setup) as adoption grows; keep `uv.lock`/Python floor current.
- **Health** — periodic tech-debt passes (the register lives in `docs/plans/`); watch the
  deprecated-API surface as PySide6 evolves.

## Release / quality gate (every version)

A version ships only when: all tests pass, ruff is clean, the GUIDE reflects new
features, the CHANGELOG is updated, and the tagged build produces a working exe.

## Key risks & watch-items

- **Performance regressions** as filters/decorations grow — profile against a
  million-line capture before each release; keep per-row work O(1).
- **Parser brittleness** on non-standard logcat formats — the single biggest correctness
  risk; prioritize in v1.2.
- **Feature sprawl vs. focus** —