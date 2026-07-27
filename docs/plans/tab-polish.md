# Plan: Tab-bar polish — status, reordering, close guard

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-24
- **Related:** [open-in-new-tab.md](open-in-new-tab.md), [device-tabs.md](device-tabs.md), [persist-tabs.md](persist-tabs.md)

## Goal

Three small tab-bar improvements that only make sense together: a tab tells you
its **state** (streaming / paused / disconnected) and **line count**, tabs can be
**dragged into order**, and closing a tab that's **actively recording** asks first.

They share one file and one concept (the tab bar), so they're planned as one
change rather than three near-empty plans.

## Scope

- **In:** (1) richer tab labels — state marker + line count; (2) `setMovable(True)`
  with the session list kept in sync; (3) a confirmation when closing a tab whose
  reader is running.
- **Out (non-goals):** tab context menus (close others / close right), detaching a
  tab into a window, tab icons or colors, and tooltips beyond what exists.

## Design

`_set_tab_label(sess)` is already the single place a tab's text is decided (it
handles `● serial` while streaming, a loaded file's `title`, and elision), so (1)
is an extension there rather than new plumbing. `_close_tab` is likewise the one
close path.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/tabtitle.py` (new) | core | Pure label building, so the rules are testable without a window: `tab_label(*, name, state, count, max_len=22) -> str` producing e.g. `● device (1.2k)`, `⏸ device (340)`, `⚠ device`, `app.log (12k)`; `format_count(n)` → `1.2k` / `3.4M`; elision with an ellipsis. Unit-tested. |
| `src/zlog/ui/main_window.py` | ui | **(1)** `_set_tab_label` derives `state` from the session (`reader` running → streaming, `paused` → paused, `want_stream` without a reader → disconnected/reconnecting, else idle) and passes the model's `rowCount()`; refresh it from the same debounced timer that updates the counts, so a chatty stream doesn't relabel per batch. **(2)** `tab_bar.setMovable(True)` + `tabMoved` → reorder `self._sessions` identically and fix `_active_index`. **(3)** `_close_tab` asks (`QMessageBox`) when `sess.reader` is running, before stopping it. |
| `tests/test_tabtitle.py` (new), `tests/test_main_window_tabs.py` | — | Pure: each state's marker, count formatting, elision with a count still visible. Window: a paused session shows the paused marker; `tabMoved` keeps `_sessions` and the active tab aligned (drag tab 0 → 1, then assert the right session is active and its model is on screen); closing a streaming tab prompts and, if declined, keeps the tab **and** the stream. |

## Architecture touch points

- **Threading:** none new — but the label now depends on the row count, so it must
  be refreshed on the existing debounced counts timer, never per batch.
- **Model/proxy:** read-only `rowCount()`.
- **Dependency direction:** label rules go in Qt-free `core/`; the window supplies
  the state.

## Risks & regressions to check

- **Reordering is the risky one:** `_sessions`, `_active_index`, and the tab bar's
  own order must stay in lockstep, or a tab shows another tab's log. `tabMoved`
  gives `(from, to)` — apply the same move to the list and recompute the active
  index; verify with the `_switch_tab` path and with a stream running in a moved
  tab.
- **Relabel cost:** per-batch label updates on a busy stream would be wasteful and
  make the count flicker — debounce.
- **Label length:** the count must not push the name out entirely; elide the name,
  keep the marker and count.
- **Close prompt** must not appear for idle/file tabs (that would be annoying),
  and declining must leave the reader running — not a half-stopped tab.
- Existing tests assert exact tab text (`"a.log"`, `"● emulator-5554"`) — adding a
  count changes those strings; update them deliberately, and consider making the
  count opt-in if it proves noisy.

## Verification

- [ ] `uv run pytest` (pure label rules + the three window behaviours)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` screenshot of a multi-tab bar showing different states
- [ ] Manual: drag a tab while it streams and confirm the right log stays with it;
      close a recording tab and decline.

## Open questions

- **Count in the label at all?** **Resolved:** on by default, but omitted entirely
  when zero so a fresh tab doesn't read "(0)". No toggle yet — add one if it grates.
- **Markers:** **Resolved:** symbols (`●` `⏸` `⚠`) in the label, with the state
  spelled out in the tooltip.
- Should reordering persist across launches (i.e. feed
  [persist-tabs.md](persist-tabs.md))? Leaning yes, for free, if both ship.
