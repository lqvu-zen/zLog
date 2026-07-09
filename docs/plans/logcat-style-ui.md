# Plan: Android-Studio-style log UI (dense, query-driven)

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-09
- **Related:** supersedes much of ui-column-polish, column-visibility, toolbar-tidy,
  empty-state-and-polish; likely closes ui-log-selection-contrast and
  ui-combo-selection-contrast. Executes the "Reading & navigation" pillar of ROADMAP.md.

## Goal

Replace the grid table + two filter rows + wide button row with a clean, dense,
**one-line-per-entry** log view like Android Studio's Logcat: a single **query bar**,
a thin **vertical icon rail**, and everything else tucked into a **⋮ overflow menu**.

## Decisions (agreed 2026-07-09)

- **Query bar:** one smart field with a lightweight syntax; prefixes map to existing
  filters, bare text is a message/tag search.
- **Existing features:** kept, moved into a compact **⋮ overflow** (menus stay reachable).
- **Controls:** a thin **vertical icon rail** down the left edge (clear, pause/follow,
  start/stop, scroll-to-end), like the screenshot.

## Scope

- **In:** the three phases below.
- **Out (non-goals):** a full query language with boolean grouping/parentheses;
  pid→package name resolution for every row (package shown only if cheaply known);
  removing any existing capability (all stay reachable via overflow).

## Design — three shippable phases

Each phase is verified and committed on its own; the app stays working between phases.

### Phase A — Line-per-entry log view (the headline)
Keep the **virtualized model** (performance is non-negotiable); change only how rows
are *presented*.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_delegate.py` (new) | ui | A `QStyledItemDelegate` that paints one entry per row: a small colored **level chip** (D/I/V/W/E/F), then monospace segments `time  pid-tid  Tag  package  message` at fixed x-offsets (table-like alignment without a grid), text tinted per level. Honors selection/hover, bookmark marker, tag/search highlight. |
| `src/zlog/ui/theme.py` | ui | Add per-level **text** colors (`level_text`) for the AS look; keep existing row tints for highlight/bookmark. |
| `src/zlog/ui/log_model.py` | ui | Collapse to a single presented column (or keep columns but the view shows col 0); expose what the delegate needs via `entry_at`. No header, no gridlines, compact row height. |
| `src/zlog/ui/main_window.py` | ui | Hide the header/grid; set the delegate; drop column-width setup. `Time`/relative-time still formats the time segment. |

### Phase B — Controls: rail + top bar + overflow
| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Replace the two filter rows + button row with: **top bar** = device combo (left) + query field (stretch) + ⋮ button (right); **left vertical `QToolBar`** of small icon buttons: Clear, Pause/Follow, Start/Stop, Scroll-to-end (and Top). Move File/View menus (theme, columns→n/a, time display, zoom, bookmarks, presets, save/open) into the ⋮ overflow menu. Keep all shortcuts. |

### Phase C — Smart query bar → filters
| File | Layer | Change |
|---|---|---|
| `src/zlog/core/query.py` (new) | core | Pure `parse_query(text) -> QuerySpec` (Qt-free, unit-tested). Tokens: `level:E` (min level or set), `tag:Foo`, `package:com.x` / `app:`, `-term` (exclude), `/regex/` (regex), quoted `"two words"`, bare tokens → message/tag search. |
| `src/zlog/ui/log_model.py` | ui | Add a `set_tag(text)` proxy gate (tag contains) if `tag:` is used. |
| `src/zlog/ui/main_window.py` | ui | On query change, `parse_query` → apply to the proxy gates (min-level/levels, search, tag, exclude, package). Invalid regex flags the field (reuse the error tint). |

## Architecture touch points

- **Virtualized model preserved** — the delegate paints only visible rows; no per-row
  widgets; O(1) per painted row. This is the single most important invariant here.
- **Qt-free `core`** — the query parser is pure and tested; the proxy gates it drives
  already exist (level/search/exclude/pids) plus the small new tag gate.
- **Dependency direction** unchanged (`ui → adb → core`).
- **Settings** — persist the query string and rail/overflow prefs via the existing spec;
  superseded keys (hidden_columns) stay accepted for back-compat, just unused.
- **Versioning:** no bump until release.

## What this supersedes / de-emphasizes

- Column headers, column widths, column-visibility, PID/TID right-align, row-banding,
  the two-row filter toolbar, and the separate match-nav/exclude widgets (their
  behavior moves into the query bar + rail + overflow). The underlying features remain.

## Risks & regressions to check

- **Performance:** scroll a million-line capture; painting must stay smooth. Profile the
  delegate; avoid per-paint allocations (precompute fonts/metrics/x-offsets).
- **Alignment:** monospace segment offsets must line up and handle long tags/messages
  (elide or let message run; soft-wrap optional later).
- **Behavior parity:** every filter reachable via the query bar; copy/save/bookmarks/
  highlight still work on the new view; selection/scroll/Follow unchanged.
- **Theme:** looks right in both Light and Dark (screenshot is dark; keep both).
- **Mount fragility:** build in a scratch dir, copy back with md5/parse/null checks.

## Verification (per phase)

- [ ] `uv run pytest` (delegate helpers + `core/query` parser tests; existing suite green)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Headless screenshot after each phase, compared to the Android-Studio reference
- [ ] Manual: stream, query with each prefix, copy/save/bookmark, Light+Dark

## Open questions

- Keep the **detail pane** (double-click/enter to expand a line), or drop it for
  max density? (Leaning: keep, collapsed by default, toggle in overflow.)
- **Soft-wrap** long messages vs elide? (Leaning: elide now, wrap toggle later.)
