# Plan: Open logs in a new tab + tab-bar “+” button

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-22
- **Related:** [device-tabs.md](device-tabs.md), [new-window.md](new-window.md), [open-recent.md](open-recent.md), [save-load.md](save-load.md)

## Goal

Keep the current recording/log intact when you open another one or start another
recording. **Open Log…** and **Open Recent** load into a **new tab** (reusing the
current tab when it's still empty and idle), labeled by the file name. A visible
**+** button on the tab bar (plus the existing Ctrl+T) makes a fresh tab to start a
new recording in — old tabs keep streaming.

## Scope

- **In:** route `open_log` / Open-Recent through a "reuse-or-new tab" helper; name a
  loaded tab by its file base name; a **+** button beside the tab bar wired to
  `_new_tab`. Tabs are already independent sessions with their own reader/model.
- **Out (non-goals):** persisting tabs across launches, per-tab settings beyond
  what LogSession already carries, drag-reorder of tabs, closing-tab confirmations.

## Design

Tabs already exist (`LogSession` per tab; `_new_tab`, `_switch_tab`, `_close_tab`),
and streaming/loading operate on the *active* session. Today `open_log` and the
Open-Recent actions call `_load_log_file(path)` on the active tab, replacing it.
We add a thin routing layer and a tab-name override; the heavy lifting (the async/
sync file load) is unchanged.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_session.py` | ui | Add `self.title = ""` — an explicit tab label (set for a loaded file); empty means "derive from device/stream state". |
| `src/zlog/ui/main_window.py` | ui | **Routing:** `open_log()` and the Open-Recent actions call `_open_log_in_tab(path)` instead of `_load_log_file(path)`. `_open_log_in_tab(path)`: if the active tab is **not** idle-empty, `_new_tab()`; then `_load_log_file(path)`; then set the active session's `title = Path(path).name` and `_set_tab_label(active)`. `_maybe_reopen_last()` keeps loading into the first tab (launch), no new tab. **Idle-empty test:** `_tab_is_reusable(sess)` = `sess.reader is None and not sess.want_stream and sess.model.rowCount() == 0 and not sess.title`. **Labeling:** `_set_tab_label` shows `sess.title` (a loaded file) when present and not streaming; a streaming tab still shows `● <serial>`; starting a stream clears `sess.title`. **+ button:** `self.new_tab_btn = QPushButton("+")` (compact, tooltip "New tab (Ctrl+T)") in an HBox with `tab_bar` in `_build_layout`, wired to `_new_tab`. Clearing a tab (`clear`) or starting a stream resets `title` so the label reflects the new content. |
| `docs/GUIDE.md` | — | Tabs paragraph: Open Log / Open Recent open in a new tab (keeping the current one); **+** or Ctrl+T starts a fresh tab to record another device; close a tab with its ×. |
| `tests/test_main_window_*` | — | Opening a file into a populated tab creates a second tab labeled by the file name; opening into a fresh idle tab reuses it (no extra tab); the **+** button adds a tab; a streaming tab keeps its `● serial` label (title not shown while streaming). |

## Architecture touch points

- **Threading:** unchanged — each tab already owns its `AdbReader`; opening/streaming
  in a new tab doesn't touch the others' threads. The large-file async loader still
  fills the *active* (new) tab's model via signals.
- **Model/proxy:** none new; `_load_log_file` already clears + fills the active
  session's model. New tab = fresh model, so the old tab's model is untouched.
- **Dependency direction:** UI-only.

## Risks & regressions to check

- Reuse rule must be conservative: only reuse a tab that's truly empty **and** not
  streaming/intending-to-stream **and** has no loaded-file title, so we never blow
  away a recording or a just-opened log.
- `_load_log_file` stops the *active* stream before loading — with the new-tab
  routing it runs on the freshly created (idle) tab, so it won't stop another tab's
  live stream. Verify the async large-file path also targets the new tab.
- Tab label precedence: streaming (`● serial`) must win over a stale `title`; starting
  a stream in a tab that previously showed a file name must switch to the device
  label (clear `title` on stream start / on clear).
- Open Recent currently loads in place — switching it to new-tab must still record
  the file in recents and not double-open.
- The **+** button + Ctrl+T + New-Tab menu all call `_new_tab`; keep one code path.
- `_maybe_reopen_last` (launch) and session-restore must not spawn a second tab.

## Verification

- [ ] `uv run pytest` (open-into-populated-tab makes a 2nd tab named by file; reuse
      an idle tab; + adds a tab; streaming label unaffected)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` scenario: load a file, then Open another → two tabs, old kept;
      screenshot the tab bar with the + button.

## Open questions

- Should **Start** streaming also auto-open a new tab if the current tab already has
  a loaded file/stream? Decision (per approval): no — recording uses the current tab;
  use **+**/Ctrl+T first to record alongside. Keeps Start predictable.
- Tab label length: elide long file names (e.g. > 22 chars) with an ellipsis and a
  full-path tooltip. Leaning yes.
