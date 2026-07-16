# Plan: Persistent highlight rules

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-16
- **Related:** ROADMAP "Reading & navigation" (P1), [tag-highlight.md](tag-highlight.md),
  [highlight-matches.md](highlight-matches.md), [settings-dialog.md](settings-dialog.md)

## Goal

After this ships, **View → Highlight Rules…** lets the user maintain a list of
term/regex → color rules that tint matching rows *all the time* — independent of
whatever's currently in the search box — so a standing rule like "tint any
FATAL/ANR line" or "always show my package in green" doesn't have to be
re-typed into the search bar and doesn't disappear when the search is cleared
or changed. Rules persist across restarts.

## Scope

- **In:** an ordered list of `{pattern, regex, color}` rules, first-match-wins;
  a **Highlight Rules…** dialog (View menu) to add/edit/remove rules and pick
  colors; rules apply as a row background tint; persisted via the existing
  settings mechanism.
- **Out (non-goals):** per-rule case-sensitivity toggle (rules are
  case-insensitive, matching the default search/tag-color behavior elsewhere),
  rule priority drag-reordering (list order = add order; remove + re-add to
  reorder), matching on fields other than tag+message, exporting/sharing rule
  sets.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/highlight_rules.py` (new) | core | Mirrors `core/presets.py`'s shape. `make_rule(pattern: str, *, regex: bool = False, color: str = "#ffeb3b") -> dict`. `normalize_rules(raw) -> list[dict]` — drop non-dicts and blank patterns, coerce types (same defensive shape as `normalize_presets`). Qt-free; `regex`/`color` validity isn't checked here (an invalid regex is caught the same way `compile_matcher` already surfaces `re.error` elsewhere — see below). |
| `src/zlog/ui/log_model.py` | ui | `LogTableModel.__init__`: `self._highlight_rules: list[tuple[Callable[[str], bool], QColor]] = []`. New `set_highlight_rules(self, rules: list[dict]) -> None`: compiles each rule's pattern once via `core.search.compile_matcher(pattern, regex)` (skip any rule whose regex fails to compile — same tolerance `set_search`/`set_exclude` already have), store `(matcher, QColor(color))` pairs, then `self._repaint_backgrounds()`. New `highlight_rules(self) -> list[dict]` returns the current rules as plain dicts (for saving) — mirrors `tag_colors()`. In `data()`, add a check in both the `Qt.BackgroundRole` block (~line 88-98) and the `HIGHLIGHT_ROLE` block (~line 103-113): after the `tag_colors` lookup and before the colorizer check, loop `self._highlight_rules` and return the first matching color. Precedence becomes: **tag color (explicit per-tag override) → highlight rule (persistent) → plugin colorizer → transient search/watch highlight → level tint** — rules sit above colorizers/search since they represent standing user intent, below the more specific per-tag override. |
| `src/zlog/ui/highlight_rules_dialog.py` (new) | ui | `HighlightRulesDialog(QDialog)` — same shape as `SettingsDialog` (pure view, takes `rules: list[dict]`, exposes `get_values() -> list[dict]`). A `QTableWidget` (Pattern / Regex checkbox / Color swatch button) + Add row / Remove selected row buttons + OK/Cancel. The color button opens `QColorDialog` and repaints its own swatch; Regex is a checkbox per row. No live preview against the log (keeps the dialog decoupled, same as `SettingsDialog`). |
| `src/zlog/ui/main_window.py` | ui | Import `HighlightRulesDialog` and `normalize_rules`. New View-menu action "Highlight Rules…" (near "Tag Summary…", line ~752) → `_show_highlight_rules_dialog()`: opens the dialog with `self.model.highlight_rules()`, on accept calls `self.model.set_highlight_rules(normalize_rules(dlg.get_values()))` and repaints (`self.table.viewport().update()`). Add `("highlight_rules", self.model.highlight_rules, lambda v: self.model.set_highlight_rules(normalize_rules(v)))` to `_settings_specs()` (line 2364), following the exact `tag_highlights` triple already there. |
| `src/zlog/core/settings.py` | core | Add `"highlight_rules": []` to `DEFAULTS` (near `"tag_highlights"`). |
| `tests/test_highlight_rules.py` (new) | tests | `normalize_rules` — drops bad entries, coerces types, mirrors `test_presets.py`'s style if one exists (else mirrors the shape of `tests/test_history.py`/similar normalize tests). |
| `tests/test_log_model.py` | tests | `set_highlight_rules` — a matching rule's color wins over level tint but loses to an explicit tag color; first-match-wins when two rules both match; an invalid regex rule is skipped without raising. |

## Architecture touch points

- **Qt-free core:** `highlight_rules.py` has zero Qt imports, matching
  `presets.py`/`history.py`; the *compiled* matchers (which need per-row
  closures, same as `_highlight`) stay in the ui layer, consistent with how
  `set_search`/`set_highlight` already work — `compile_matcher` itself is the
  Qt-free primitive shared by both.
- **New dialog stays decoupled:** `HighlightRulesDialog` takes/returns plain
  data (`list[dict]`), no back-reference to `MainWindow`/`LogTableModel` —
  same contract as `SettingsDialog`.
- **Persistence via the existing `_settings_specs()` triple** — no new save/load
  plumbing, just one more `(key, get, set)` row, so it can't drift from how
  every other setting persists.
- **Repaint only, no model reset:** matches `set_tag_color`/`set_highlight`'s
  existing `_repaint_backgrounds()` (a `dataChanged` emit over `BackgroundRole`),
  not `beginResetModel`.

## Risks & regressions to check

- **Invalid regex rule:** must not crash `set_highlight_rules` or block the
  dialog from closing — skip that one rule (mirrors `set_search`'s tolerance),
  and Ruff/tests should cover it.
- **Color precedence surprises:** confirm a highlighted tag still visually wins
  over a highlight rule (explicit per-tag choice is more specific), and that a
  highlight rule still shows even while actively searching for something else
  (the "always highlighted regardless of the current search" requirement) —
  this depends on the rule check running unconditionally, not gated behind
  `self._highlight is not None`.
- **Performance:** rules are evaluated per visible row per repaint, same cost
  class as the existing single `_highlight` predicate — keep the rule list
  small in practice (dialog doesn't need a cap, but note it if it becomes an
  issue after real use).
- **Settings round-trip:** rules must survive save → restart → load with
  colors and regex flags intact (covered by the `_settings_specs()` triple
  test pattern already used for `tag_highlights`).

## Verification

- [x] `uv run pytest` (355 passed; 1 pre-existing unrelated timing flake, see
      crash-anr-detector.md)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Smoke / screenshot via `run-zlog` (new `highlight-rules` scenario):
      FATAL EXCEPTION rows tinted red by the persistent rule while WifiService
      rows are simultaneously tinted blue by an active Highlight-mode search —
      confirms the rule doesn't depend on the search box
- [x] Manual: `tests/test_log_model.py` covers precedence (tag color beats
      rule, rule beats level tint), first-match-wins, and settings round-trip
      via `_settings_specs()` (covered by the existing
      `test_specs_cover_exactly_defaults` guard)

## Open questions

None — precedence order and scope are decided above; flag during review if a
different precedence is wanted.
