# Plan: Split main_window.py (construction + capture controller)

- **Status:** In progress  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-24
- **Related:** [refactor-main-window.md](refactor-main-window.md), [tech-debt-refactor.md](tech-debt-refactor.md), [windows-app-focus.md](windows-app-focus.md), [windows-debug-output.md](windows-debug-output.md)

## Goal

Cut `src/zlog/ui/main_window.py` (3,599 lines, 212 methods — ~40% of all source)
down to a coordinating window, by moving widget/menu construction into builders
and the four duplicated reader-start paths behind one testable capture
controller. No behavior changes, no new features.

## Why now

Measured, not guessed:
- `main_window.py` = 3,599 lines / 212 methods. Next largest file is 783.
- Construction is ~590 lines in three methods: `_build_menus` (214),
  `_build_widgets` (159), `_build_layout` (135) — pure assembly, no logic.
- Four near-identical start paths (`_start_reader`, `start_merged`,
  `capture_debug_output`, `launch_app`) each repeat: connect
  `batch_ready`/`error`, set `sess.reader/serial/title/stream_label/paused/
  pause_buffer`, call `_set_tab_label`, then set the same toolbar state.
  `_set_streaming_controls` was already extracted mid-feature — the tell that
  the rest wants extracting too.

Explicitly **not** in scope, and why:
- `_settings_specs` (240 lines) is the largest method but the *best* design in the
  file — one `(key, get, set)` table so save/restore can't drift. Leave it.
- `log_model.py` (783) is coherent (model + proxy) and heavily tested.
- Layering is already clean: no Qt in `core/`, no `zlog.ui` imports in
  `core`/`adb`/`winlog`. This plan must not change that.

## Scope

- **In:** (1) extract construction into `ui/build.py` (widgets/layout) and
  `ui/menus.py` (menu bar); (2) introduce `ui/capture_controller.py` owning
  reader attach/detach so the four start paths share one wiring path.
- **Out (non-goals):** renaming public methods the tests/driver call
  (`start`, `stop`, `open_log`, `capture_debug_output`, `launch_app`, `focus_app`
  stay put), touching `_settings_specs`, changing any behavior or UI, splitting
  `log_model.py`, or reworking `tests/test_main_window_settings.py` beyond what
  the move forces.

## Design

Two independent phases, each landing separately so a regression is easy to bisect.
`MainWindow` keeps every attribute it exposes today (`self.table`, `self.query`,
`self.start_btn`, …) — builders **assign onto the window** rather than inventing a
new indirection, so the ~1,300 existing test references keep working untouched.

### Phase A — construction extraction (mechanical, lowest risk)

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/build.py` (new) | ui | `build_widgets(win)` and `build_layout(win)` — the current bodies of `_build_widgets`/`_build_layout`, taking the window and setting the same attributes on it. No logic moves; only location. |
| `src/zlog/ui/menus.py` (new) | ui | `build_menus(win)` — the body of `_build_menus`, including the action objects it stores on the window (`win.capture_debug_act`, `win.launch_app_act`, `win.redact_action`, the theme group, buffer/tail action dicts, …). |
| `src/zlog/ui/main_window.py` | ui | `_build_widgets`/`_build_layout`/`_build_menus` become one-line delegations to the new functions, preserving the documented call order from `__init__`. Expected: **~590 lines out**. |

### Phase B — capture controller (the design win)

One place that knows how to attach a reader to a session and tear it down.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/capture_controller.py` (new) | ui | `CaptureController(QObject)` holding the window's session-agnostic capture logic: `attach(sess, reader, *, label=None, primary=True)` — connects `batch_ready` → the window's `_on_batch(sess, …)`, `error` → the window's error slot, optional `stream_ended`; sets `sess.reader` (primary) or appends to the extra-readers list; resets `title`/`stream_label`/`paused`/`pause_buffer`; returns the reader. `detach(sess)` — stops the primary + extras, clears state. Owns the `_merged_readers` list (renamed `extra_readers`). No widget access: it emits/returns, the window updates toolbar + tab label — so it unit-tests with a fake reader and a bare `LogSession`, like `DeviceController`. |
| `src/zlog/ui/main_window.py` | ui | `_start_reader`, `start_merged`, `capture_debug_output`, `launch_app` each build their reader then call `self.capture.attach(...)` + `self._set_streaming_controls()` + `self._set_tab_label(sess)`. `stop()` calls `self.capture.detach(sess)` then restores controls. Behavior identical, duplication gone. |
| `tests/test_capture_controller.py` (new) | — | Attach wires the signals and sets session state; a second attach as non-primary lands in extras; `detach` stops **both** primary and extras and clears `reader`; attaching a launch reader sets the stream label. Uses a stub reader (plain `QObject` with the three signals), no adb/Windows. |

## Architecture touch points

- **Threading:** unchanged. Readers still run off-thread and reach the UI only via
  signals; the controller only centralizes *where those connections are made*.
  The `lambda e, x=sess: ...` default-arg binding (which pins the right session)
  must be preserved exactly.
- **Model/proxy:** untouched. No new gate, column, or role.
- **Dependency direction:** all new modules are `ui/`; they import `adb`/`winlog`/
  `core` but nothing imports `ui`. `core/` stays Qt-free.

## Risks & regressions to check

- **Mount-write corruption on a 3,600-line file** — this file has corrupted on
  large edits repeatedly (truncation that can still `ast.parse`). Mitigation:
  small edits, verify each with `ast.parse` + null-byte scan + marker greps +
  a full test run, and commit each step separately so `git HEAD` is always a
  clean recovery point.
- **Construction order** — `__init__` calls widgets → layout → menus → connect in
  a documented order; several attributes are created in one and used in the next.
  Moving must not reorder them.
- **Attribute coverage** — every `self.x` a builder creates must still exist
  afterwards; verify by running the *whole* suite (~1,300 window-attribute uses)
  plus the `run-zlog` driver, which pokes `window.model`, `window.proxy`,
  `window.search`, `window._populate_devices` directly.
- **Session pinning** — the per-reader lambdas must keep binding their own
  session, or batches from one tab would land in another.
- **Teardown** — `stop()` must still stop the primary reader *and* every extra
  (merged AdbReaders, the DBWIN companion of a launched app) with no orphaned
  child process or thread; `closeEvent` likewise.
- **`_merged_readers` rename** — grep every use (window + tests) before renaming;
  keep a property alias if anything external reads it.
- **Public surface** — `start`/`stop`/`open_log`/`capture_debug_output`/
  `launch_app`/`focus_app` keep their names and signatures (tests + skills call them).

## Verification

- [ ] `uv run pytest` — full suite green after **each** phase (not just at the end)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` driver: `smoke` + `populated` + `two-tabs` render identically
      (compare screenshots before/after — construction moved, pixels shouldn't)
- [ ] `wc -l src/zlog/ui/main_window.py` drops by ~590 (A) and ~150 (B)
- [ ] Manual: start/stop an adb stream, merged view, debug capture, launch an app —
      each starts, labels its tab, and stops cleanly with no orphan process.

## Open questions

- **Split menus further?** `_build_menus` is 214 lines; File/View could be
  separate functions. Leaning one `build_menus(win)` first — smaller diff, easy to
  subdivide later.
- **Builders as functions vs. a `WindowBuilder` class?** Leaning plain functions
  taking `win`: least ceremony, no new state, trivial to move back if it doesn't help.
- **Should `CaptureController` own `_on_batch` too?** It's 32 lines of pause/
  autoscroll/watch logic that touches widgets. Leaning no — keep widget work in the
  window; the controller stays widget-free and testable.
- **Do Phase B first?** It's the real design win, but Phase A is safer and proves
  the edit-and-verify loop on this fragile file. Leaning A then B.
