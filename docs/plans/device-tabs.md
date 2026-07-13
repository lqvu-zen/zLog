# Plan: Tabbed device view (concurrent streams in one window)

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v2.0 (multiple device tabs), [new-window.md](new-window.md)

## Goal

One window hosts several capture tabs, each an independent device stream with its
own model/filters/bookmarks; the shared toolbar/menus act on the active tab.

## Approach (least-invasive, staged, each stage committed)

`self.model`/`self.proxy` are assigned once and referenced ~90 times. Rather than
edit every call site, introduce a `LogSession` (model+proxy+reader+stream state)
and make `MainWindow.model`/`proxy`/`reader`/pause/reconnect **properties that
delegate to the active session**. Existing method bodies then operate on the
active tab unchanged; only stream *routing* (batch/stream-ended/reconnect, which a
background reader can fire) becomes session-aware.

- **Stage 1 (this):** add `LogSession`; re-root the window to a single active
  session. Behavior identical; all tests stay green. *(commit)*
- **Stage 2:** a `QTabBar`; New Tab (Ctrl+T) + closable tabs; on switch, swap the
  table's model and save/restore the per-tab toolbar state (device, query, level).
  *(commit)*
- **Stage 3:** route `on_batch`/`_on_stream_ended`/`_try_reconnect` by the emitting
  session so background tabs keep streaming concurrently. *(commit)*

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_session.py` | ui | `LogSession(parent)` builds its own `LogTableModel`+`LogFilterProxy` and holds `reader`, `serial`, `query`, pause/reconnect state and a reconnect `QTimer`. |
| `src/zlog/ui/main_window.py` | ui | Stage 1: `_sessions`/`_active_index`; `_make_session()`; properties `model`/`proxy`/`reader`/`_paused`/`_pause_buffer`/`_want_stream`/`_reconnect_serial`/`_last_time`/`_reconnect_timer` → active session. Stages 2–3 add the tab bar and routing. |

## Risks & regressions to check

- **Property ordering:** the first session is created in `_build_widgets` before any
  `model`/`proxy` use; `_active_index` defaults to 0.
- **Signal rebinding (Stage 2):** proxy-driven signals (counts/heat/placeholder/
  selection) must follow the active proxy on tab switch.
- **Concurrency (Stage 3):** a background reader's batch must append to *its*
  session, not the visible one.

## Verification

- [ ] Stage 1: `uv run pytest` (210) green with the re-rooting — no behavior change.
- [ ] Stages 2–3: new tab tests; ruff clean each stage.
