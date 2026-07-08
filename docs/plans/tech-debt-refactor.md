# Plan: Tech-debt refactor (Phases 2–3)

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-07-07
- **Related:** phase1-cleanup.md (done, Phase 1), refactor-main-window.md (done)

## Goal

Close the highest-value gaps from the tech-debt register: give the `ui/` and `adb/`
layers a real test safety net that actually runs in CI, de-duplicate the adb
error handling, and extract a device/filter controller — so the bugs that keep
appearing in `main_window`/`log_model` get caught automatically instead of by hand.

## Scope

- **In:**
  1. **UI/adb test coverage** — headless tests for the proxy filter
     gates and the settings round-trip, plus `adb/` parsing/threading seams.
  2. **CI runs Qt tests** — a CI job that installs the offscreen Qt
     deps and runs the new tests so they gate merges.
  3. **De-duplicate adb error handling** — `refresh_devices`, `load_packages`, and
     `apply_package_filter` each repeat the same `FileNotFoundError` / generic
     `Exception` → status-bar-message shape; fold into one helper.
  4. **Controller extraction** — move device listing/selection + package/PID
     filtering + PID tracking out of `MainWindow` into a `DeviceController`
     (deferred from refactor-main-window.md), making that logic unit-testable
     without a full window.
  5. **Python floor / lockfile docs** and settings-parity in CI
     (the settings-spec parity check, which falls out of item 2's CI job).
- **Out (non-goals):** new user-facing features; changing the on-disk settings
  format; rewriting the reader's batching/threading model.

## Design

Do it in the register's phase order; each phase is independently shippable.

### Phase 2 — safety net (test coverage, then CI)

| File | Layer | Change |
|---|---|---|
| `tests/test_log_model.py` | test | Headless (`QT_QPA_PLATFORM=offscreen`) tests for `LogFilterProxy`: level gate, text/regex/case search gate, package-PID gate, and their combination; `LogTableModel.append_entries` virtualized-append + counts. |
| `tests/test_main_window_settings.py` | test | Round-trip: set non-default widget state → `_save_settings` → fresh window → `_load_and_apply_settings` → assert every widget matches; assert `_settings_specs()` keys == `DEFAULTS`. |
| `.github/workflows/ci.yml` | infra | Add a step installing `libegl1 libxkbcommon0 libgl1 libglx0` and running pytest under `QT_QPA_PLATFORM=offscreen`, so ui/adb tests gate merges. |

### Phase 3 — dedupe + controller (items 3 and 4)

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Extract an `_adb_guard(action, *, on_missing, on_error)` helper (or a small context manager) that maps `FileNotFoundError` → "adb not found" and generic failures → a message; use it in `refresh_devices`, `load_packages`, `apply_package_filter`. |
| `src/zlog/ui/device_controller.py` (new) | ui | `DeviceController(QObject)` owning the device list, `_preferred_serial`, package/PID filter state, and `_track_new_pids`; exposes signals/methods the window binds to. `MainWindow` shrinks to wiring. |
| `tests/test_device_controller.py` | test | Unit-test selection preference, package filter set/clear, and live PID tracking without constructing a `MainWindow`. |

## Architecture touch points

- **Threading:** unchanged — reader stays a `QThread` emitting batched signals; the
  controller touches widgets only via signals/slots on the main thread.
- **Dependency direction:** `ui → adb → core` preserved. The controller lives in
  `ui/` (it needs `QObject`); any Qt-free logic it needs (e.g. serial preference)
  can move to `core/`. `core/` stays Qt-free and CI-testable without a display.
- **Model/proxy invariant:** tests assert the master list stays complete and filtering
  happens through the proxy.
- **Versioning:** no bump (release-only).

## Risks & regressions to check

- Offscreen Qt in CI: pin the apt packages; the run-zlog driver already proves the
  offscreen path works, so reuse its setup.
- Controller extraction must not change behavior: the Phase-2 tests are the guardrail
  — land them *first*, then refactor under green.
- adb-guard helper must preserve today's exact status-bar messages (assert them).
- **Dev-mount corruption** (observed this session): commit before starting, verify
  each write with parse + null-byte + md5-stable checks, prefer building in a stable
  scratch dir and copying back.

## Verification

- [ ] `uv run pytest` (new ui/adb/controller tests green)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] CI: the new offscreen-Qt job passes on a PR
- [ ] Behavior parity: device pick, package filter apply/clear, PID re-track on
      restart, and every settings key still round-trips after the controller extraction
- [ ] `run-zlog` smoke screenshot unchanged

## Open questions

- Controller as a single `DeviceController`, or split device-picking from
  package/PID filtering into two? Leaning one to start; split if it grows.
- Is Python `>=3.14` a hard requirement, or can the floor drop to 3.12 to widen
  contributor/CI support?
