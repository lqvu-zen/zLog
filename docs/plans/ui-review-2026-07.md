# Plan: UI review — full app pass (July 2026)

- **Status:** Done
- **Owner:** Claude (review-zlog-ui)
- **Created:** 2026-07-13
- **Related:** [ui-review-polish.md](ui-review-polish.md), [match-navigation.md](match-navigation.md), [severity-navigation.md](severity-navigation.md), [bookmarks.md](bookmarks.md), [device-tabs.md](device-tabs.md), [clear-device-button.md](clear-device-button.md), [level-counts.md](level-counts.md), [showing-count.md](showing-count.md)

## Goal

Fix the concrete, source-verified defects found in a full-app UI/UX pass: a
keyboard-shortcut collision that silently breaks two navigation features, a
status-bar summary that misrepresents itself once a filter is active, an
always-on match counter that's invisible, a tab-close affordance that lies, and
an inconsistent pair of destructive/non-destructive buttons sitting side by side.

## Findings
**Screens reviewed:** idle/empty, populated, filtered (level), devices, package
filter, regex search, opened-from-file, dark theme, empty (no device), no-match,
copy-selection, bookmarks, match navigation, tag highlight, detail pane,
guide states (streaming / dark / level / package) · **Screenshots:**
`smoke-idle.png`, `populated.png`, `filtered-warn-and-above.png`, `devices.png`,
`package-filter.png`, `regex-search.png`, `opened.png`, `dark.png`, `empty.png`,
`no-match.png`, `copy.png`, `bookmarks.png`, `match-nav.png`, `highlight.png`,
`details.png`, `guide-streaming.png`, `guide-dark.png`, `guide-level.png`,
`guide-package.png` (all re-generated fresh via `driver.py` for this review).

### High
> Hurts usability or looks broken.

#### H1. F2 / Shift+F2 is bound to two unrelated features at once
- **Screen / location:** `src/zlog/ui/main_window.py:571-576` (Next/Previous
  **Problem** — severity navigation) and `main_window.py:613-618` (Next/Previous
  **Bookmark**). Both are `QAction`s on the same `QMainWindow` with the literal
  shortcuts `"F2"` / `"Shift+F2"`.
- **What & why:** Qt refuses to resolve an ambiguous shortcut shared by two
  actions in the same window context — it does not "pick one," it fires
  neither (and Qt prints an "Ambiguous shortcut overload" warning). So today,
  pressing F2 activates **neither** "jump to next warning/error" nor "jump to
  next bookmark" — both `severity-navigation.md` and `bookmarks.md` shipped as
  Done, but their signature shortcuts silently don't work whenever both
  features are wired up (i.e. always, since both live in the same window).
  This is the kind of bug that's invisible in code review (each plan's diff
  looked correct in isolation) and invisible in a screenshot — it only shows up
  by triggering the shortcut.
- **Recommendation:** Give bookmarks a distinct shortcut pair, since "Problem"
  navigation more directly matches the mnemonic F2 already documents in the
  View menu's "Next Problem" label from the earlier, solo plan. Suggest
  `Ctrl+F2` / `Ctrl+Shift+F2` for bookmarks (bookmarks are a *manual* markers
  list, so a modifier distinguishing them from the *automatic* severity jump is
  reasonable), or `Alt+Down`/`Alt+Up`. Whichever is chosen, add one
  `tests/` case (or a quick manual check) that presses both shortcuts and
  confirms each fires its own handler — this class of bug won't be caught by
  existing tests since none exercise `QShortcut`/`QAction` activation.

#### H2. The status-bar level tally silently describes the wrong set once filtered
- **Screen / location:** `main_window.py:1629-1638` calling
  `core/summary.py:format_level_summary()`. Visible in `filtered-warn-and-above.png`,
  `package-filter.png`, `regex-search.png`, `no-match.png`.
- **What & why:** `format_level_summary` was built by two separate plans
  layered on one line: `level-counts.md` added the `F:n E:n W:n …` tally (always
  computed from `self.model.level_counts()` — the **entire captured buffer**),
  and `showing-count.md` later prefixed `"Showing X of Y lines"` when a filter
  narrows the view. The two reads as one sentence but describe two different
  populations: e.g. `regex-search.png` shows **"Showing 16 of 56 lines  F:8 E:8
  W:16 D:8"** — a user reading that will assume the counts describe the 16
  matched lines, but they're the totals for all 56 captured lines (the filter
  hid 40 of them, several of which are counted in that W:16/D:8). This is a
  correctness-flavored UX bug: the status bar states something false-by-implication
  with total confidence, and it's the one place a user checks "how many
  errors am I looking at" while triaging a filtered log — precisely when
  getting it wrong matters most.
- **Recommendation:** Compute the level tally from the filtered set when a
  filter is active (iterate proxy rows the same way `_match_rows` already does,
  or add a cheap `LogFilterProxy.level_counts()` that maps to source rows), and
  keep the current full-buffer tally as a secondary/tooltip figure — e.g.
  `"Showing 16 of 56 lines  F:2 E:6 W:8  (56 total: F:8 E:8 W:16 D:8)"`, or
  simpler: only show the tally for the *visible* set and drop total-buffer
  breakdown when filtered (unfiltered case is unaffected either way, since
  `visible == total` there).

### Medium
> Noticeable friction or inconsistency.

#### M1. Match navigation (F3 / Shift+F3) has zero visible feedback
- **Screen / location:** `main_window.py:398-399` builds `self.match_label`
  (intended to show `"N matches"` and, while stepping, `"n/total"` — see
  `_update_match_label`/`_goto_match`, `main_window.py:998-1018`), but it is
  never passed to `addWidget`/`addPermanentWidget` anywhere in `_build_layout`
  or `_build_menus`. Same for `match_prev_btn`/`match_next_btn`
  (`main_window.py:392-397`) — built, wired to `_goto_match`, never placed.
  `match-navigation.md` is marked Done.
- **What & why:** The feature works (F3/Shift+F3 do jump between matches,
  confirmed by reading `_goto_match`), but a user gets no on-screen indication
  of *how many* matches exist or *which one* they're currently on — the only
  feedback is the row scrolling into view. For a "step through N matches"
  feature, that's the one piece of information the label exists to show, and
  it's silently discarded.
- **Recommendation:** Add `self.match_label` to the filter row (next to
  `self.query`, e.g. `filter_row.addWidget(self.match_label)`), matching the
  design already implied by its `setMinimumWidth(64)`. The `match_prev_btn`/
  `match_next_btn` are lower priority to surface (F3/Shift+F3 already cover
  the interaction) — either place them next to the label for mouse users or
  delete them if keyboard-only is the intended UX; don't leave them built and
  wired but permanently invisible, since that's dead weight future readers
  have to rule out.

#### M2. The device tab's close (×) button is shown — and clickable-looking — even when it can't do anything
- **Screen / location:** `main_window.py:300-304` (`self.tab_bar.setTabsClosable(True)`
  applies to every tab unconditionally) vs. `main_window.py:218-220`
  (`_close_tab` silently `return`s when `len(self._sessions) <= 1`). Visible in
  every screenshot — `smoke-idle.png`, `populated.png`, `devices.png`, etc. all
  show a "Device ⊠" tab with a live-looking close glyph.
  the single default tab.
- **What & why:** Every screenshot in this review — including the ones from
  before device tabs existed — now shows a small red × next to "Device" that
  looks exactly as clickable as a real close button, but clicking it is a
  silent no-op. A new user's first instinct when they see an × next to
  something is "this closes it"; here nothing visibly happens, with no
  explanation, which reads as broken rather than intentional.
- **Recommendation:** Hide the close button on a tab when it's the only one
  left, and show it again once a second tab exists — `QTabBar` supports this
  via `tab_bar.setTabButton(0, QTabBar.RightSide, None)` when
  `len(self._sessions) == 1`, restored via `_new_tab`/`_close_tab`. This keeps
  `setTabsClosable(True)` for the common multi-tab case while not offering a
  button that does nothing on the common single-tab case (device tabs are a
  power feature — most sessions only ever have one tab open, per
  `device-tabs.md`'s own framing as "concurrent device streams").

#### M3. "Clear" (view) and "Clear device" sit next to each other with mismatched affordance for very different blast radius
- **Screen / location:** `main_window.py:436-446` (glyph-button loop covers
  `clear_btn` but not `clear_device_btn`) and `main_window.py:458-459`
  (`top_row.addWidget(self.clear_btn)` immediately followed by
  `top_row.addWidget(self.clear_device_btn)`). Visible in every device-bar
  screenshot as "✕" then "Clear device".
- **What & why:** `clear_btn` clears the local view only (cheap, fully
  reversible — logs are still on the device) and is rendered as a bare "✕"
  glyph relying entirely on a tooltip to be understood. `clear_device_btn`
  sits directly to its right, is fully labeled "Clear device", and runs
  `adb logcat -c` — it wipes the device's actual logcat buffer, which is not
  undoable and (per `clear-device-clears-view.md`) also clears the view. Two
  actions of very different severity, placed adjacently, styled inconsistently
  (one glyph-only, one full text) is a misclick risk in exactly the wrong
  direction: the *safe* action is the unlabeled one, the *destructive* action
  is one key-repeat away from it.
- **Recommendation:** Either (a) give `clear_device_btn` a glyph too and add a
  confirmation-free but visually distinct treatment (e.g. keep it text-labeled
  specifically *because* it's destructive — text is slower to parse than a
  glyph, which is a reasonable deliberate speed bump — and instead move
  `clear_btn`'s ✕ away from it with more `addSpacing`/a separator), or (b) add
  a `_vsep()` between them (already used elsewhere on this exact row for
  grouping) so they don't read as one cluster. Prefer (b): it's a one-line
  change consistent with how the row already separates Package/Level groups,
  and it preserves clear_device_btn's deliberate full-text weight as a mild
  "this one's different" signal.

### Low
> Polish.

#### L1. `driver.py`'s `columns` scenario is stale and fails
- **Screen / location:** `.claude/skills/run-zlog/scripts/driver.py:202-206`
  references `window._column_actions`, which no longer exists — column
  visibility was retired when the log view moved to the single-line
  Android-Studio-style row (`logcat-style-ui.md`, also noted in
  `CLAUDE.md`'s `ui/log_delegate.py` row). Confirmed by running it: it raises
  `AttributeError` before writing a screenshot.
- **What & why:** Not a UI defect (there's no column-visibility feature to
  review anymore), but it's a broken verification tool — anyone running the
  full scenario sweep (as this review just did) hits a traceback and might
  mistake it for an app regression.
- **Recommendation:** Delete `scenario_columns` and its `"columns"` entry in
  `SCENARIOS`, and remove `columns.png`/`toolbar-tidy.png` from the
  screenshots folder description in `SKILL.md` if referenced (screenshots
  themselves are gitignored, so no cleanup needed there). Out of scope for
  this plan's `src/zlog/ui/*` change — flagging for a separate 2-line cleanup,
  not bundling it here since it touches the skill, not the app.

### What already works well
- **Theming** (`ui/theme.py`) is exactly the centralized, token-based system
  the project docs describe — Light and Dark both keep row-tint text legible,
  selection/hover states are explicit (avoiding the Qt "fixed color breaks
  auto-contrast" trap the file's own comments call out), and checkboxes show a
  real filled indicator instead of a suppressed native glyph. Don't disturb
  this while fixing the above.
- **Empty and no-match states** are good citizens of heuristic #5: "No logs
  yet — pick a device and press Start, or open a saved log (File → Open)." and
  "No lines match the current filters." are specific and actionable, not bare
  blank tables.
- **Severity color coding** (row tint + colored level chip + colored message
  text, all three redundant) means color-blind users aren't solely dependent
  on hue — the level letter is always present too.
- **The single query-bar redesign** is coherent: `level:`/`tag:`/`package:`/
  `-exclude`/free-text all funnel through one full-width row with a visible
  syntax hint placeholder, and `_apply_query`'s docstring is explicit that it's
  "the one place filtering is applied in the new UI" — that clarity is *why*
  H1/H2/M1 above were findable at all (the intent is legible in the code, it's
  the follow-through — wiring, layout, shortcut allocation — that has gaps).

### Deferred
- **Dead/orphaned widgets beyond `match_label`** — `self.exclude` (a
  `QLineEdit`, superseded by the query bar's `-exclude` token),
  `self.clear_filters_btn` (superseded by the View → "Clear Filters" menu
  action), `self.search_mode_box` (superseded by View → Search options →
  "Highlight matches") are all built, wired to live signal handlers, and never
  placed in any layout. None of them cause a user-visible problem (their
  functionality is reachable another way, unlike `match_label`), so fixing
  this is pure code hygiene, not a UI/UX fix — deferred to a separate
  tech-debt pass (candidate for `docs/ROADMAP.md`) rather than folded into
  this plan.
- **Sparkline appears as uniform-height bars in every screenshot** — checked
  this against `core/sparkline.py`; it's an artifact of the driver's `SAMPLE`
  data being a fixed 7-line cycle repeated verbatim, which produces a
  genuinely near-constant error rate across buckets. Not a rendering bug — no
  action needed, but noting it so a future reviewer doesn't re-investigate the
  same dead end.

## Scope

- **In:** H1 (shortcut collision), H2 (status-bar tally scope), M1 (match
  label visibility), M2 (single-tab close affordance), M3 (Clear/Clear device
  adjacency).
- **Out (non-goals):** L1 (driver script fix — separate, not a `ui/*` change),
  the Deferred dead-widget cleanup, any new features.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | H1: change bookmark shortcuts to `Ctrl+F2`/`Ctrl+Shift+F2` (`main_window.py:614,617`) |
| `src/zlog/ui/main_window.py`, `src/zlog/ui/log_model.py` (or a new `LogFilterProxy.level_counts()`) | ui / ui | H2: tally from the filtered set when `visible < total` |
| `src/zlog/core/summary.py` | core | H2: `format_level_summary` signature/behavior for a filtered tally (keep pure + tested) |
| `src/zlog/ui/main_window.py` | ui | M1: `filter_row.addWidget(self.match_label)` in `_build_layout` |
| `src/zlog/ui/main_window.py` | ui | M2: `_new_tab`/`_close_tab` toggle `tab_bar.setTabButton(0, QTabBar.RightSide, …)` based on session count |
| `src/zlog/ui/main_window.py` | ui | M3: insert `self._vsep()` + spacing between `clear_btn` and `clear_device_btn` in `_build_layout`'s `top_row` |

## Architecture touch points

- **Threading:** none of these touch the reader thread or `batch_ready` path.
- **Model/proxy:** H2 needs either a new `LogFilterProxy` method that counts
  levels across currently-accepted rows, or reuse of the `_match_rows`-style
  proxy-row iteration already in `main_window.py`. Must not mutate the master
  list or defeat virtualization — this is a read-only tally over
  `proxy.rowCount()`, same cost class as the existing `_update_counts`.
- **Dependency direction:** `core/summary.py` stays Qt-free; if the filtered
  tally needs proxy access, do the row-walk in `ui/main_window.py` (or
  `ui/log_model.py`) and hand `core.summary.format_level_summary` a plain
  `dict[str, int]` as it already expects — don't push Qt types into `core`.

## Risks & regressions to check

- H1: confirm both shortcuts fire their own action after the change (no
  Ambiguous-shortcut warning in stderr when running the app and pressing
  F2/Shift+F2 and the new bookmark bindings).
- H2: recompute cost must stay cheap enough to run on every `rowsInserted` /
  `layoutChanged` signal (same trigger set as today's `_update_counts`) even
  at high row counts — reuse the existing bounded/virtualized proxy iteration
  pattern, don't materialize the whole filtered set eagerly if it can be
  avoided.
- M2: `QTabBar.setTabButton(index, side, None)` semantics — verify removing
  and re-adding the button doesn't leak the old button widget or break
  `tabCloseRequested` wiring for the remaining tabs' indices after a close.
- M3: purely cosmetic spacing change — verify the row doesn't overflow/clip at
  the app's default window width after adding a separator.
- General: none of these touch `AdbReader`, `append_entries`, or autoscroll —
  low blast radius, but re-run the full scenario sweep since several findings
  came from states (`filtered`, `regex-search`, `match-nav`) that are easy to
  regress silently.

## Verification

- [x] `uv run pytest` — 213 passed.
- [x] `uv run ruff check .` and `uv run ruff format --check .` — clean.
- [x] Shortcut collision fixed by construction: `next_problem_act`/`prev_problem_act`
      keep bare `F2`/`Shift+F2`; `next_bm`/`prev_bm` now use `Ctrl+F2`/
      `Ctrl+Shift+F2` — grepped `setShortcut(` afterward to confirm all four
      strings are distinct (no headless way to prove keyboard activation, but
      Qt's ambiguous-shortcut resolution is the actual root cause and it no
      longer applies once the strings differ).
- [x] Re-shot `smoke`, `filtered`, `regex-search`, `no-match`, `match-nav`,
      `devices` via `run-zlog` and read each: H2's tally now matches the
      visible set (`regex-search.png`: "Showing 16 of 56 lines E:8 W:8", not
      the old full-buffer "F:8 E:8 W:16 D:8"; `no-match.png` drops the tally
      entirely when nothing's visible); M1's `<`/`>`/match-position label are
      visible on the filter row and `match-nav.png` shows "1/6"; M2's single
      "Device" tab has no close ×; M3's Clear/Clear device now sit in visibly
      separate groups.
- [x] Added a `two-tabs` scenario to `driver.py` and shot it — opening a
      second tab restores a real close (×) button on both tabs, confirming
      `_update_tab_closability` isn't a one-way trip.

## Open questions

- H1: is `Ctrl+F2`/`Ctrl+Shift+F2` acceptable for bookmarks, or does the user
  have a different mnemonic preference (e.g. swap which feature keeps bare
  F2)? Either works code-wise; this is a product call.
- M2: should the close button reappear only once ≥2 tabs exist (proposed), or
  should the tab bar itself hide entirely with a single tab (bigger change,
  more consistent with "power feature stays out of the way" but changes the
  always-on chrome more than this plan's blast radius should).
