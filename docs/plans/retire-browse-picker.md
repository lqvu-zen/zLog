# Plan: Replace Browse… with Launch App… on the App row

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-29
- **Related:** [unify-app-filter.md](unify-app-filter.md), [windows-app-focus.md](windows-app-focus.md)

## Goal

Swap the App row's **Browse…** button for **Launch App…**, so starting a fresh
capture is one click from the row that already handles filtering to an app.

## Why

[unify-app-filter.md](unify-app-filter.md) folded Browse's job — picking a
running process by name — into Load/Apply's merged, marked list. The only thing
Browse still did that Load/Apply can't is pin one exact PID before it's logged
anything, and that's a narrow case already covered by right-click → **Filter
to… → PID** once a line exists. A dedicated picker dialog for that residual case
no longer earns its spot in the row. **Launch App…** — already in the File menu —
is a much more common action (start capturing something) and deserves the
front-row button more than a picker whose main job is now redundant.

## Scope

- **In:** remove `focus_app_btn` / `focus_app()` / `ProcessPickerDialog` and its
  call sites; add a `launch_app_btn` to the App row wired to the existing
  `launch_app()` (no behavior change there — same method the File menu action
  already calls); delete the now-dead picker plumbing (`process_dialog.py`,
  `filter_processes`) and their tests.
- **Out (non-goals):** changing what `launch_app()` does; changing the App
  box/Load/Apply merge logic from unify-app-filter.md; removing the File →
  **Launch App…** menu entry (the button supplements it, same as Start/Stop/etc.
  already duplicate menu actions); touching `ProcessInfo` / `sort_processes` /
  `list_processes` / `focus_query` (still used by the merge path and by
  `launch_app()` itself to focus on the app it just started).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Delete the `focus_app()` method. `launch_app()` is untouched. |
| `src/zlog/ui/build.py` | ui | Remove `focus_app_btn` creation/tooltip/connect; add `win.launch_app_btn = QPushButton("Launch App…")` with a tooltip, `.clicked.connect(win.launch_app)`, placed in the App row where Browse… was (same spot in `top_row`). |
| `src/zlog/ui/process_dialog.py` | ui | Delete — `ProcessPickerDialog` has no remaining caller. |
| `src/zlog/core/procinfo.py` | core | Remove `filter_processes` (its only consumer was the picker's search box). Also removed `ProcessInfo.label` (only caller was the deleted `focus_app`'s status message) — not in the original table, but the same "no remaining caller" cleanup. Keep `ProcessInfo`, `sort_processes`, `focus_query`. |
| `tests/test_app_focus.py` | tests | Remove the picker-dialog tests (`test_picker_*`) and the `focus_app` window tests (`test_focus_app_*`); keep the `launch_app` tests; add a test that `launch_app_btn` exists and triggers `launch_app`. Rename the file's docstring/scope accordingly. |
| `tests/test_procinfo.py` | tests | Remove the `filter_processes` tests; keep `sort_processes`/`focus_query`/`merge_candidates`/`strip_marker` coverage. |
| `docs/GUIDE.md` | — | In "Focusing on one app", drop the Browse…/picker description; note Launch App… now sits on the App row too (it already has its own "Launching the app from zLog" section — cross-reference rather than duplicate). |

## Architecture touch points

- **Threading:** none — pure UI removal/rewire, `launch_app()`'s existing
  `LaunchReader` threading is untouched.
- **Model/proxy:** none.
- **Dependency direction:** unaffected; deleting `process_dialog.py` only removes
  a `ui`-layer file.

## Risks & regressions to check

- No other code imports `ProcessPickerDialog` or `zlog.ui.process_dialog` (only
  `main_window.focus_app` did — confirmed by grep before starting).
- `filter_processes` has no other caller before deleting it (confirmed).
- The App row still reads as one control group after the swap (Load, Apply,
  Clear app, Launch App…) — check with a screenshot.
- `launch_app_btn` must reuse `launch_app()` exactly as the File menu action
  does, so tab-reuse/clear-on-start/dbwin-alongside behavior is unchanged.

## Verification

- [x] `uv run pytest` — 683 passed, 3 pre-existing failures in
      `test_main_window_settings.py` unrelated (same ones confirmed against a
      clean `main` while implementing unify-app-filter.md)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` screenshot of the App row with the new button (`smoke-idle.png`
      — Load, Apply, Clear app, Launch App…)
- [x] Grep confirms no leftover references to `focus_app`, `ProcessPickerDialog`,
      or `process_dialog` outside this plan/history

## Open questions

None — scope confirmed with the user: drop the picker entirely rather than
relocating it.
