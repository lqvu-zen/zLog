# Plan: Remember last-used device

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-06
- **Related:** device-picker.md, settings-persistence.md

## Goal

Reselect the device you used last time when zLog reopens (and prefer it after a
Refresh), instead of always defaulting to the first streamable device.

## Scope

- **In:** persist the selected device **serial** (`last_device`) and, when the picker
  is populated, prefer that serial if it's present and streamable; otherwise fall back
  to the first streamable device (current behavior).
- **Out:** remembering a device that's no longer connected (nothing to select), auto
  starting the stream on launch, or remembering per-device filters.

## Design

The serial is a stable id; persistence already exists (`core/settings.py` +
`_load_/_save_settings`). Add one key and a "preferred serial" the population code
consults.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/settings.py` | core | Add `"last_device": ""` to `DEFAULTS`. |
| `src/zlog/ui/main_window.py` | ui | Track `self._preferred_serial`; `_populate_devices` selects it when present (else first streamable); remember it whenever the user picks a real device; load it in `_load_and_apply_settings` and reselect; save it in `_save_settings`. |

## Architecture touch points

- **Model/threading:** none. Pure picker + settings wiring on the main thread.
- **Dependency direction:** UI reads/writes via pure `core.settings`; core stays Qt-free.
- **Versioning:** no bump.

## Risks & regressions to check

- Saved device gone on next launch → falls back to first streamable, no crash.
- `currentIndexChanged` fires during population (before settings load) → the preferred
  serial is only *read* there; the saved value overwrites it right after.
- The run-zlog driver injects fake devices via `_populate_devices` → must still pick a
  sensible default when `_preferred_serial` is None.

## Verification

- [ ] `uv run pytest` (incl. settings round-trip with the new key)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Headless: populate fake devices with `_preferred_serial` set → that serial is
      selected; unset/absent → first streamable selected
- [ ] Manual: pick device B, close, reopen → B preselected
