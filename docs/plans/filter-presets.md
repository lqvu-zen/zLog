# Plan: Saved filter presets

- **Status:** Draft
- **Owner:** Vũ
- **Created:** 2026-07-08
- **Related:** settings-persistence, clear-filters, package-filter, regex-search

## Goal

Save the current filter combo (min level + search text + regex + case + package) under
a name and re-apply it later from a menu, persisted across launches — for repeated
debugging workflows ("crashes only", "my app errors").

## Scope

- **In:** **View → Filter Presets** submenu with "Save current filter as…" (name prompt)
  and one entry per saved preset that re-applies it; a way to delete a preset. Presets
  persisted in settings.
- **Out:** presets that also capture theme/columns/device; import/export; per-project
  presets.

## Design

A preset is a small dict of the existing filter fields; applying one just drives the
existing widgets (which push through the proxy). Pure list logic can live in `core`.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/presets.py` (new) | core | `Preset` shape + validate/normalize helpers (Qt-free, unit-tested). |
| `src/zlog/core/settings.py` | core | Add `"filter_presets": []` to `DEFAULTS`. |
| `src/zlog/ui/main_window.py` | ui | Build the Presets submenu; `_current_filter()` snapshots the widgets; `_apply_preset(p)` sets level/search/regex/case and applies the package (skipping the adb PID resolve when offline, or re-resolving if streaming). Save/delete rebuild the submenu; persisted via the settings spec. |

## Architecture touch points

- Applying a package preset reuses `apply_package_filter` (needs a live device for PID
  resolve); when offline, the package text is set but PIDs resolve on next Apply. Documented.
- Presets stored as plain JSON-able dicts (settings stays Qt-free and format-stable).
- Menu rebuild on save/delete; no model/proxy change beyond existing setters.
- Versioning: no bump.

## Risks & regressions to check

- Corrupt/old preset entries are ignored, not fatal (validate on load).
- Applying a preset routes through the same setters as manual filtering (one code path).
- Round-trip of `filter_presets`; spec-parity assert holds; Clear Filters unaffected.

## Verification

- [ ] `uv run pytest` (core presets tests + settings round-trip incl. filter_presets)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Headless: save a preset, change filters, re-apply → widgets + proxy match
