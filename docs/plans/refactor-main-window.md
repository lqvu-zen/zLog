# Plan: Refactor main_window (slim __init__ + declarative settings)

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-07
- **Related:** settings-persistence.md, remember-device.md (the last-device bug this
  refactor is designed to prevent recurring)

## Goal

Make `src/zlog/ui/main_window.py` (662 lines, 36 methods, ~46% of the codebase)
easier to read and safer to change — with **no behavior change** — by breaking up the
197-line `__init__` and removing the load/save settings duplication that let a saved
key drift from a restored key.

## Scope

- **In (two behavior-preserving refactors):**
  1. **Split `__init__`** into focused helpers it calls in order:
     `_build_widgets()`, `_build_layout()`, `_build_menus()`, `_connect_signals()`
     (plus the existing `_load_and_apply_settings()`). `__init__` becomes a short
     orchestrator.
  2. **Declarative settings table.** Replace the two hand-maintained key lists in
     `_load_and_apply_settings` / `_save_settings` with a single list of settings
     specs — each `(key, getter, setter)` — that both methods iterate. Adding a
     setting becomes one entry in one place.
- **Out (non-goals):**
  - No new user-facing feature, no menu/toolbar/label wording changes, no layout
    changes visible in a screenshot.
  - **Not** extracting a `DeviceController`/`FilterController` (bigger, riskier — a
    separate later plan if we want it).
  - No version bump (release-only policy).
  - No change to `core/settings.py`'s on-disk JSON format or `DEFAULTS`.

## Design

Pure `ui/` refactor. Same widgets, same signals, same saved keys — only their
*organization* changes.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Extract `__init__` body into `_build_widgets`/`_build_layout`/`_build_menus`/`_connect_signals`. Introduce `self._settings_specs()` returning a list of specs; rewrite `_load_and_apply_settings` and `_save_settings` to loop over it. Order-sensitive restores (geometry, theme before `apply_theme`, device reselect after populate) are preserved by spec ordering and a couple of explicit steps kept outside the loop where needed. |

### Settings-spec shape

Each spec pairs a key with how to read it from a widget and how to apply it back:

```python
Spec(key, get=lambda: <value to save>, set=lambda v: <apply to widget>)
```

`_save_settings` builds `{s.key: s.get() for s in specs}`; `_load_and_apply_settings`
calls `s.set(data.get(s.key, DEFAULTS[s.key]))`. Values needing validation/ordering
(theme must be a known name and applied via `apply_theme`; `last_device` must reselect
only after the picker is populated; `hidden_columns`/`tag_highlights` iterate
collections) live in their spec's `set`, so the special-casing is co-located with the
key instead of scattered.

## Architecture touch points

- **Threading:** none. No reader/`QThread` changes; batching untouched.
- **Model/proxy:** none. No new column or filter predicate.
- **Dependency direction:** unchanged — still `ui → adb → core`; `core/settings.py`
  stays Qt-free and its API (`load_settings`/`save_settings`, `DEFAULTS`) is unchanged.
- **Colors rule:** out of scope here, but noted — `_apply_search`'s hard-coded regex
  tint should later move into `ui/theme.py` (tracked separately, not in this plan).

## Risks & regressions to check

- **Silent truncation of `main_window.py`** during edits (happened during
  remember-device). Mitigate: after each edit, `wc -l` + `grep '    def '` to confirm
  all 36 methods still present and re-read is stable; keep a git commit before starting
  so recovery is trivial.
- Settings **round-trip parity**: every key in `DEFAULTS` is both saved and restored
  (assert the spec key set == `DEFAULTS.keys()`), so no key can silently drop out.
- **Restore ordering**: theme applied before dependent repaints; `last_device`
  reselected after `_populate_devices`; follow/min-level/regex still push through the
  proxy. Verify the window still opens with saved state applied.
- No change to the rendered UI (toolbars, menus, status bar) — confirm by screenshot.

## Verification

- [ ] `uv run pytest`  (add a test asserting the settings-spec key set matches
      `DEFAULTS` so save/restore can't drift)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` smoke + a before/after screenshot are identical (no visual change)
- [ ] Headless settings round-trip: set non-default values on a window, `_save_settings`,
      construct a fresh window, `_load_and_apply_settings`, assert every widget matches
- [ ] `grep -c '    def '` and `wc -l` before/after to prove no method was lost to a
      truncated write

## Open questions

- Keep the settings spec inline in `main_window.py`, or move the spec list to a small
  `ui/settings_binding.py`? Leaning inline for now (it references widgets); revisit if
  a `DeviceController` extraction later makes a separate module natural.
