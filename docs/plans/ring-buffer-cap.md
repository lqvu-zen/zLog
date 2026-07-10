# Plan: Bounded ring-buffer (cap the master list)

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-09
- **Related:** [tail-count.md](tail-count.md), [log-buffers.md](log-buffers.md),
  ROADMAP v1.2 "Capture & scale"

## Goal

After this ships, a long or high-volume capture can't grow memory without bound:
the model keeps at most the last N entries (user-chosen), dropping the oldest as
new lines arrive, while staying virtualized and keeping counts/bookmarks correct.

## Why

`LogTableModel._rows` currently grows forever. On a busy device an all-day
capture is millions of entries — eventually memory-bound. A cap makes zLog safe
to leave running. Default stays **Unlimited** so nothing changes unless asked.

## Scope

- **In:** a `max_rows` cap on `LogTableModel` (0 = unlimited), enforced on every
  append via `beginRemoveRows`; a **View → "Buffer limit"** exclusive submenu
  (Unlimited / 10k / 50k / 100k); persisted as a `max_rows` setting.
- **Out:** disk spillover / paging to a file, per-buffer caps, a visible "dropped
  N lines" indicator (counts already reflect the retained set).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_model.py` | ui | Add `self._max_rows = 0`. `set_max_rows(n)` clamps to `>=0` and calls `_enforce_cap()`. New `_enforce_cap()`: if capped and `len(_rows) > max`, `beginRemoveRows(0, overflow-1)`, drop `_rows[:overflow]`, decrement `_level_counts` for each dropped entry (delete key at 0), remap `_bookmarks` to `{i-overflow for i in ... if i>=overflow}`, `endRemoveRows()`. Call `_enforce_cap()` at the end of `append_entries`. `_baseline` stays (elapsed-since-capture-start is a stable reference even if its row is trimmed). |
| `src/zlog/core/settings.py` | core | Add `"max_rows": 0` to DEFAULTS. |
| `src/zlog/ui/main_window.py` | ui | Build a `View → Buffer limit` `QActionGroup` (Unlimited=0 / 10000 / 50000 / 100000), wire `triggered` → `self.model.set_max_rows(n)`; add a `max_rows` settings spec `(getter, setter)` that checks the matching action and applies to the model. |
| `tests/test_log_model.py` | tests | Cap trims oldest & preserves order; counts decrement; bookmarks remap (and drop trimmed ones); raising/clearing the cap is a no-op when under it. |
| `tests/test_main_window_settings.py` | tests | `max_rows` persists and the menu applies it to the model. |

## Architecture touch points

- **Virtualized model:** trimming uses `beginRemoveRows`/`endRemoveRows` (never
  `beginResetModel`), so the view stays virtualized and only repaints deltas.
- **Threading:** unchanged — `append_entries` still runs on the main thread from
  the `batch_ready` slot; trimming happens there too.
- **core stays Qt-free:** only a DEFAULTS key is added.

## Risks & regressions to check

- **Bookmark remap:** indices must shift down by `overflow` and drop any that fall
  below 0 — otherwise bookmarks point at the wrong (or invalid) rows.
- **Count sync:** `level_counts()` and `rowCount()` must stay consistent so the
  status bar total matches the retained set.
- **Selection/scroll:** removing front rows shifts indices; Follow-mode autoscroll
  should still pin to the bottom (it keys off the scrollbar, not row indices).
- **delta time mode:** the new row 0 shows delta 0 (references itself) — cosmetic,
  acceptable.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] New model tests cover trim/order/counts/bookmark-remap.
- [ ] Manual sanity: set 10k, stream, confirm the row count plateaus at 10k and
      the newest lines keep arriving.
