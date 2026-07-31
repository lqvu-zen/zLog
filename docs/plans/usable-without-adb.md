# Plan: zLog stays usable without adb

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-30
- **Related:** [local-source-in-device-box.md](local-source-in-device-box.md), [device-picker.md](device-picker.md), [windows-debug-output.md](windows-debug-output.md), [custom-adb-path.md](custom-adb-path.md)

## Goal

A Windows user with **no Android platform-tools installed** can still pick
**This PC (debug output)** and press **Start**. Today they can't — the device
picker is empty and disabled, so the Windows capture flow is unreachable.

## The bug

`refresh_devices()` bails out before populating anything when `adb` is missing:

```python
devices = self._run_adb(...)   # FileNotFoundError -> reports, returns None
if devices is None:
    return                      # <- returns here
self._populate_devices(devices) # <- never runs
```

`_populate_devices` is the **only** place the local "This PC" entry is added
(see `local-source-in-device-box.md`), so with no adb the picker keeps its
construction-time state.

Reproduced in this repo at `bfa5106` (shipped in 1.1.0) by stubbing
`list_devices` to raise `FileNotFoundError` and forcing `is_supported() -> True`:

```
device_box items  : ['No devices']
device_box enabled: False
Start enabled     : False
```

Severity: the Windows debug-capture feature exists precisely for people
debugging Windows apps, who have no reason to have Android tooling. The
File-menu items (Capture Debug Output, Launch App…, Follow File…) do stay
enabled, so it's a dead *primary path*, not a dead app — but the GUIDE tells
users to "pick This PC → Start", which cannot be done.

**Why the tests missed it:** every existing test calls `_populate_devices(...)`
directly, and `test_run_adb_reports_missing_adb` only asserts that `_run_adb`
returns `None` and reports a message. Nothing exercises `refresh_devices()` with
a failing adb and then inspects the picker. The bug lives exactly in the gap
between those two functions.

## Scope

- **In:** make `refresh_devices` populate with an empty device list instead of
  returning early, so local sources still appear; make the adb-missing message
  non-alarming when the user isn't using Android; a regression test through
  `refresh_devices` (not `_populate_devices`).
- **Out (non-goals):** bundling adb, auto-downloading platform-tools, hiding
  Android UI wholesale on adb-less machines, and changing `custom-adb-path`
  (Settings already lets users point at an adb elsewhere).

## Design

One-line behaviour change plus honest messaging. `_populate_devices([])` already
does the right thing — it adds the local entry on Windows and only falls into the
disabled "No devices" state when there's genuinely nothing to offer.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | `refresh_devices`: on failure call `self._populate_devices([])` instead of returning, so local sources are still listed and Start stays usable. Keep reporting the adb problem, but demote it: when at least one local source exists, phrase it as informational ("No adb found — Android devices unavailable. This PC is still available.") rather than an error implying breakage. Track whether adb was found so **Refresh** can retry cleanly. |
| `src/zlog/ui/main_window.py` | ui | `_show_device_error` shouldn't shout when the user may not care about Android — status bar only, no modal, and don't repeat it on every refresh (the existing adb-error dedupe pattern applies). |
| `docs/GUIDE.md` | — | State plainly that adb is only needed for Android devices; the Windows sources work without it. |
| `tests/test_main_window_adb.py` | — | **The missing test:** drive `refresh_devices()` with `list_devices` raising `FileNotFoundError` and assert the picker still offers the local entry, is enabled, and Start is enabled (with `is_supported` forced True); and that off Windows it degrades to today's "No devices" disabled state. Cover the message, too. |

## Architecture touch points

- **Threading:** none.
- **Model/proxy:** none.
- **Dependency direction:** unchanged; this is UI-flow only.

## Risks & regressions to check

- **Don't hide a real adb problem.** Someone who *is* debugging Android and has a
  broken PATH must still learn why no devices appear — the message stays, it just
  stops being framed as fatal.
- **Non-Windows with no adb** must behave exactly as today (disabled "No devices"
  picker), since there are no local sources to offer. Easy to regress by making
  the population unconditional.
- **Refresh after installing adb** must recover without a restart — verify the
  retry path repopulates real devices.
- **`_populate_devices([])` on Windows** must not leave a stale disabled state:
  confirm the box is re-enabled when the local entry is present.
- The existing "No devices" branch runs when `devices` is empty **and** no local
  entry was added; check that ordering still holds after the change.
- **This bug class is the real lesson:** tests that call the inner function
  directly can't see a caller that never reaches it. Prefer driving the public
  entry point (`refresh_devices`) in at least one test per flow.

## Verification

- [x] New regression test fails before the fix, passes after (verified
      explicitly: stashed the `main_window.py` fix, reran the new tests —
      3 failed as expected — then restored the fix and they passed).
- [x] Targeted tests only (`tests/test_main_window_adb.py`,
      `tests/test_main_window_settings.py`, `tests/test_main_window_dbwin.py`)
      — 99 passed. Full-suite run deferred to a release/QA pass, not per-fix
      (see [[no-full-suite-per-feature]]).
- [x] `uv run ruff check .` and `uv run ruff format --check .` both clean.
- [x] Manual on Windows with adb removed from PATH: launched a real `MainWindow`
      in a subprocess with adb's directory stripped from `PATH` (confirmed
      `shutil.which("adb") is None`, not mocked) — This PC was listed,
      enabled, preselected, and Start was enabled. Restored adb on `PATH` and
      pressed Refresh: recovered cleanly ("0 device(s) found.", no crash, no
      stale disabled state).
- [ ] Manual on Linux/macOS with no adb — not performed (no such machine
      available here); covered by
      `test_refresh_devices_non_windows_still_shows_no_devices_when_adb_missing`
      (forces `is_supported() -> False`), which is the same substitution used
      by every other cross-platform test in this codebase
      (e.g. `test_main_window_dbwin.py`).

## Open questions (resolved)

- **Should the adb error appear at all on first launch?** Yes — show it once in
  the status bar, not on every refresh. A Windows-only user shouldn't be nagged
  about Android tooling on repeat refreshes.
- **Offer a hint in the message?** Yes — a short status-bar hint (e.g. point at
  Settings → adb path), not a dialog.
- Worth auditing the other `_run_adb` callers for the same early-return shape
  (`load_packages`, dumpsys, Wi-Fi connect)? They're user-initiated rather than
  startup, so the failure is self-explanatory there — but worth a look.
