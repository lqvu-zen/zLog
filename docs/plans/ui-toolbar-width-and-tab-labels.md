# Plan: UI review — device-bar minimum width and local-source tab labels

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-31
- **Related:** [ui-polish-adb-status.md](ui-polish-adb-status.md), [two-bar-header.md](two-bar-header.md), [toolbar-tidy.md](toolbar-tidy.md), [single-header-bar.md](single-header-bar.md), [local-source-in-device-box.md](local-source-in-device-box.md)

## Goal

zLog's window can actually be resized to fit common laptop screens, and a tab
left on **This PC** shows a name a user recognizes instead of an internal
identifier.

## Findings
**Screens reviewed:** two open tabs, wrap-mode-at-a-narrow-width, copy
selection, bookmarks, incidents, match navigation, Highlight mode, persistent
highlight rules, Jank Summary, inline match highlight (wide + narrow/wrapped),
font family, line numbers, density (compact/comfortable), Isolate, duplicate
collapsing, stack-trace folding, time-range filter, the merged App-box load,
package filter (proxy- and query-driven), regex search, an opened log.
**Screenshots:** `two-tabs.png`, `wrap-refit.png`,
`inline-match-highlight-wrap.png`, plus the rest in
`.claude/skills/run-zlog/screenshots/` (all reshot fresh this pass).

### High

#### H1. The window has a hard ~1671px minimum width — narrower than many laptop screens
- **Screen / location:** every screen; root cause in
  `src/zlog/ui/build.py:124` (`win.device_box.setMinimumWidth(180)`) and
  `build.py:149` (`win.package_box.setMinimumWidth(220)`), compounded by
  ~15 more buttons/labels sharing the same unwrapped `QHBoxLayout` row
  (`build.py:251-282`, `top_row`)
- **What & why:** `MainWindow.__init__` requests `self.resize(1100, 700)`
  (`main_window.py:166`), but the device bar's *content* — two wide
  hardcoded-minimum comboboxes plus about fifteen more controls, all in one
  row with no wrap/scroll/elide — has a combined `minimumSizeHint()` of
  **1579px**, which the window's own minimum (1671px, measured directly via
  `MainWindow().minimumWidth()`) can never go below. Confirmed live: right
  after construction the window is already 1671×700, not the requested
  1100×700 — the `resize(1100, 700)` call is dead code today, silently
  overridden. Concretely, this means the window **cannot be narrowed below
  1671px no matter what the user does** — not manually, not via saved
  geometry, not by a scenario driving `resize()` directly (this is how the
  bug was found: `scenario_inline_match_highlight_wrap`'s
  `window.resize(500, 400)` only ever took the height). A 1671px floor is
  wider than a 1366×768 or 1440×900 laptop panel — extremely common
  hardware — and rules out ever putting zLog in a half-screen/tiled layout
  on anything short of a genuinely wide monitor. This is heuristic #7
  ("the window resizes... check narrow and wide") failing outright at the
  narrow end, not just looking cramped.
- **Recommendation:** Two moves, one now and one deferred (see Scope):
  trim `device_box`'s and `package_box`'s hardcoded minimums now (they were
  sized generously, not load-bearing at their current values) — a real,
  low-risk width reduction, though not by itself enough to reach a genuinely
  narrow floor. The actual fix (letting the bar reflow, scroll, or split
  across two rows so there's no hard floor at all) is a bigger structural
  change and belongs in its own plan — see Deferred.
- **Screenshot:** `inline-match-highlight-wrap.png` (window visibly wider
  than its own 500px resize request)

#### H2. A "This PC" tab's label shows the raw internal id, not a name
- **Screen / location:** the tab strip — `src/zlog/ui/main_window.py:318-330`
  (`_set_tab_label`), fed by `main_window.py:294`
  (`sess.serial = self.device_box.currentData() or ""`)
- **What & why:** `_set_tab_label` falls back to the bare `sess.serial`
  string when a tab is idle and has no title (`name = sess.title or
  sess.serial or "Device"`). For a real adb device that's fine — a serial
  like `emulator-5554` **is** the recognizable name. But for the local
  pseudo-device, `sess.serial` is the internal sentinel `local:dbwin`
  (`core/devices.py`'s `LOCAL_DBWIN`), and it leaks straight onto the tab:
  opening a second tab while **This PC** is selected in the first produces a
  tab literally labeled **"local:dbwin (28)"**. The device *dropdown* right
  below it, showing the same source, correctly reads "This PC (debug
  output)" — so the same session is described two different ways six
  pixels apart, and the tab's way is an implementation detail no user should
  ever see.
- **Recommendation:** Resolve through the same label logic the dropdown
  already uses instead of the raw serial: `Device(serial, "device").label`
  (from `core.devices`, already imported in this file) returns "This PC
  (debug output)" for a local source and the bare serial unchanged for a
  real device — so real devices keep exactly today's behavior. Apply it to
  both `name = ...` fallbacks in `_set_tab_label` (lines 325 and 327).
- **Screenshot:** `two-tabs.png` (first tab reads "local:dbwin (28)")

### What already works well
- Multi-row selection, Highlight-mode row tinting, persistent highlight
  rules, and inline match highlighting all layer cleanly — level chip
  colors and colored message text both stay legible over every one of
  these backgrounds, in every combination screenshotted. Don't touch the
  layering order.
- Query chips (`pid:1287`, `tag:AndroidRuntime`, `since:12:34:56.110`,
  `proc:com.example.app`) consistently mirror the query bar and the status
  line wherever the real UI-driven path sets them (`package-from-log.png`)
  — confirms `level-query-sync.md`/`preset-save-full-query.md`'s
  two-way-sync work is holding up under new features built since.
- Density presets, the line-number gutter, duplicate-count badges (`×N`),
  and collapsed stack-trace frames (`▶ ... N frames`) are all subtle,
  correctly aligned, and don't fight the row's monospace grid.
- `wrap-refit.png` confirms wrap mode itself re-flows text correctly once a
  row is wide enough to need it — H1 is about *reaching* a narrow width,
  not about wrap mode being broken.

### Deferred
- **Actually letting the device bar go narrow** (not just trimming two
  comboboxes) needs a real design decision — wrap to a second row below
  some width threshold, put it in a horizontal `QScrollArea`, or start
  eliding button text — each has different tradeoffs and touches a bar
  that's already been through three dedicated passes
  (`two-bar-header.md`, `toolbar-tidy.md`, `single-header-bar.md`). Worth
  its own plan rather than a bolt-on here; H1's in-scope fix (trim the two
  hardcoded minimums) is a real but partial improvement in the meantime.
- **The Bookmarks dock** wasn't driven open in `scenario_bookmarks` (only
  the in-row bookmark markers were), so it went unreviewed this pass —
  worth a follow-up screenshot, not folding into this plan.
- **The theme editor and highlight-rules *editor* dialogs** (as opposed to
  their *effects*, which were reviewed) have no driver scenario yet and
  weren't looked at.

## Scope

- **In:** H1's *partial* mitigation (trim the two hardcoded `setMinimumWidth`
  calls) and H2 (resolve local-source tab labels through `Device.label`).
- **Out (non-goals):** A structural device-bar reflow/scroll/wrap redesign
  (see Deferred); the Bookmarks dock and editor-dialog follow-ups (see
  Deferred).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/build.py` | ui | `device_box.setMinimumWidth(180)` → a smaller value (~130px — still fits a typical adb serial or "This PC (debug output)" without truncation); `package_box.setMinimumWidth(220)` → ~160px. |
| `src/zlog/ui/main_window.py` | ui | `_set_tab_label` (lines 325, 327): replace the bare `sess.serial` fallback with `Device(sess.serial, "device").label if sess.serial else ""`, so a local pseudo-serial resolves to its friendly name and a real serial is unaffected. |

## Architecture touch points

- **Threading:** none — both changes are widget construction / label
  formatting on the main thread.
- **Model/proxy:** none.
- **Dependency direction:** unchanged; both changes stay within `ui`, and
  H2 reuses an already-imported `core.devices.Device`.

## Risks & regressions to check

- H1: confirm the two comboboxes still show a real adb serial (up to ~20
  chars, e.g. `0A2B1C3D4E5F1234`) and "This PC (debug output)" without
  eliding/clipping at their new minimums — this is a *reduction*, not a
  redesign, so don't shrink past what real content needs.
- H1: the window still won't reach a genuinely narrow width after this
  change alone (see Deferred) — verify the new floor is measurably lower,
  not that narrow resizing is fully fixed (it isn't, by design of what's
  in-scope here).
- H2: a real device's tab label must be pixel-identical to today
  (`Device(serial, "device").label` returns the bare serial unchanged for
  any non-local, streamable serial) — this must not touch the
  `stream_label` branch or anything about a *file* tab's title.
- Don't regress `tab-polish.md`'s state marker / count / elision — `H2`
  only changes what string feeds `tab_label(name, ...)`, not `tab_label`
  itself.

## Verification

- [x] Targeted tests — `tests/test_main_window_tabs.py` (22 passed, including
      2 new: `test_idle_local_source_tab_shows_friendly_name`,
      `test_idle_real_device_tab_still_shows_bare_serial`). Full suite
      deferred to a release/QA pass.
- [x] `uv run ruff check .` and `uv run ruff format --check .` clean.
- [x] Re-measured `MainWindow().minimumWidth()`: **1671px → 1561px** (−110px,
      matching the ~110-160px trimmed off the two comboboxes). Confirms H1's
      in-scope fix is real — and confirms, as documented, that this alone
      doesn't reach a genuinely narrow floor (1561px is still wider than a
      1366/1440px laptop panel; see Deferred for the actual fix).
- [x] Re-shot `two-tabs` — first tab now reads "This PC (debug outpu…(28)"
      (elided by the existing tab-width truncation, same as any other name —
      not `local:dbwin`).
- [x] Test: `test_idle_real_device_tab_still_shows_bare_serial` covers the
      real-device-unchanged case directly.

## Open questions

- None — both in-scope fixes are small and don't need a design decision
  beyond approving the plan. The real open question (how to make the device
  bar genuinely narrow-friendly) is intentionally left to the deferred
  follow-up plan, not decided here.
