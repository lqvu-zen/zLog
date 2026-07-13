# Plan: Command palette (Ctrl+K)

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v2.0 (command palette), [menu-bar.md](menu-bar.md)

## Goal

After this ships, Ctrl+K opens a searchable palette listing every menu command;
type to fuzzy-filter, Enter (or click) to run it — so any action is reachable
without hunting through menus.

## Scope

- **In:** collect the current menu actions (File/View + submenus), a modal
  palette (search box + list) with substring/subsequence matching, run on
  Enter/activate; Ctrl+K to open.
- **Out:** commands that aren't menu items, recent-command history, custom
  keybinding editor, actions with arguments.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/palette.py` | core | `match_commands(labels, query) -> list[int]` — indices of labels matching `query` (case-insensitive), ranked: substring first (by position), then subsequence; empty query returns all in order. Pure. |
| `src/zlog/ui/main_window.py` | ui | `_all_commands()` walks `menuBar()` (into submenus) collecting leaf `QAction`s with text (label = text minus `&`/`…`). `_open_command_palette()` builds a `QDialog` (search `QLineEdit` + `QListWidget`); `textChanged` re-filters via `match_commands`; Enter/`itemActivated` closes then `action.trigger()`. Ctrl+K shortcut. Imports `QListWidget`/`QListWidgetItem`. |
| `tests/test_palette.py`, `tests/test_main_window_settings.py` | tests | `match_commands` ranking/empty/no-match; `_all_commands()` includes known labels (e.g. "Open Log", "Tag Summary"). |

## Architecture touch points

- **Pure/tested matching** in core; the UI collects actions live (so dynamic menus
  like Open Recent are included) and triggers the real `QAction`.
- **No new state:** the palette is transient; it just invokes existing actions.

## Risks & regressions to check

- **Trigger timing:** `accept()` the dialog before `trigger()` so actions that open
  their own dialog don't nest oddly.
- **Separators/submenrus:** skip separators; recurse submenus; skip menu headers.
- **Disabled actions:** still listed but triggering a disabled action is a no-op
  (acceptable) — or filter to enabled; list all for discoverability.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: Ctrl+K, type "tag", Enter opens Tag Summary.
