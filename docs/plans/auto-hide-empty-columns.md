# Plan: Auto-hide PID·TID/Tag when a capture never has them

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-30
- **Related:** [fixed-columns-middle-elide.md](fixed-columns-middle-elide.md), [message-min-half.md](message-min-half.md), [column-header-labels.md](column-header-labels.md)

## Goal

A tab whose source never populates PID/TID or Tag (Windows debug-output and
Launch App captures never set TID; a followed plain-text file may have none of
the structured fields) stops reserving dead space for it — the segment appears
the moment a row actually has the data, and stays gone until then.

## Why

`LogItemDelegate` already sizes Time/PID content-adaptively via
`LogTableModel.time_col_chars()`/`pidtid_col_chars()`, but both are floored to a
minimum width (`_TIME_MIN_W`, `_PIDTID_MIN_W`) that's always applied — so the
PID·TID segment is never truly zero, even when **every** row in the capture has
left it blank. Two real sources hit this today: `winlog.dbwin` and
`winlog.launcher` never set `tid` (`OutputDebugString`/stdout carry no thread
id), and `core.parser.parse_line`'s raw fallback (an arbitrary followed text
file, `file-follow.md`) leaves every structured field blank. Right now those
rows just show a bare `1234-` (trailing dash, no tid) or empty brackets, in a
segment that's reserving width for nothing.

## Scope

- **In:** `LogTableModel` tracks, per instance (i.e. per tab — resets on
  `clear()`), whether *any* appended row has ever had a non-empty `pid`, `tid`,
  or `tag`; `LogItemDelegate` collapses the PID·TID segment to zero width when
  neither has ever appeared, and the Tag segment to zero width when it never
  has. A row with `pid` but no `tid` (or vice versa) shows just that one value,
  no stray separator.
- **Out (non-goals):** hiding Time (always meaningful once `level` is set — an
  entirely unparsed row already takes a different, columnless paint path) or
  Level (it's a colored chip, not a text column); auto-hiding the Process
  column (`show_process`, already an explicit Settings toggle — untouched);
  re-hiding a segment after it's appeared once in the current tab (one-way
  latch, matching "auto show... when it has new info" — not "auto hide again
  the moment content thins out", which would make the layout flicker while
  reading a live stream).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/models.py` | core | New `LogEntry.pidtid` property: `"pid-tid"` when both are set, else whichever one is (or `""`). Pure, unit-tested. |
| `src/zlog/ui/log_model.py` | ui | `LogTableModel` gains `_has_pid`/`_has_tid`/`_has_tag` bools (default `False`), OR'd in inside `append_entries()`'s existing per-row loop (same place `_time_col_chars`/`_pidtid_col_chars` already update), reset in `clear()`. New getters `has_pidtid() -> bool` (`_has_pid or _has_tid`) and `has_tag() -> bool`. |
| `src/zlog/ui/log_delegate.py` | ui | `plan_tag_proc_widths` gains a `show_tag` param (alongside the existing `show_proc`, renamed from `show` for clarity) — zero width/no gap when off, same shrink-to-fit math otherwise. `_col_widths` reads `src.has_pidtid()`/`src.has_tag()` (via the same `getattr(..., None)` defensive pattern already used for the char-count getters) and zeroes `pid_w` when absent, passing `has_tag` through to `plan_tag_proc_widths`. `seg()` skips *both* the draw call and its trailing gap when `width_px` is `0` (today a zero-width segment still eats one gap — harmless while the floor made that impossible, a real gap once segments can be truly zero). `_msg_left` mirrors that (skip a component's `+ gap` when its width is `0`) so it stays in exact sync with `seg()`'s x-advance without threading extra flags through it. Paint's PID·TID `seg()` call switches from `f"{entry.pid}-{entry.tid}"` to `entry.pidtid`. |
| `tests/test_log_model.py` | tests | `has_pidtid`/`has_tag` start `False`; flip `True` the first time a row supplies either; survive further empty rows; reset on `clear()`. |
| `tests/test_log_delegate.py` | tests | Update `plan_tag_proc_widths` call sites for the new `show_tag` param (pure arithmetic, no behavior change when both flags are `True`, matching today). New cases: `show_tag=False` collapses tag width and its gap to `0`; `_col_widths` against a model that never got a pid/tid/tag returns `pid_w == tag_w == 0`; against one that has returns the same values as before this change. |
| `tests/test_models.py` (or wherever `LogEntry` is tested) | tests | `pidtid` property: both set, pid-only, tid-only, neither. |

## Architecture touch points

- **Threading:** none — pure model/delegate bookkeeping, no background work.
- **Model/proxy:** no new column, no new filter — this is paint-time layout
  only, tracked on the *master* model (not the filter proxy), so segments don't
  flicker in/out while typing a search filter; they reflect what the whole
  capture has ever contained, not what's currently visible.
- **Dependency direction:** unaffected; `LogEntry.pidtid` stays in `core`,
  everything else stays `ui`.

## Risks & regressions to check

- `sizeHint` and `paint` **must stay pixel-identical** in their layout math —
  they already share `_col_widths`/`_msg_left`; verify wrap-mode row heights
  are still correct once a segment can be genuinely `0` px (an existing wrap
  test exercises this path).
- A tab that starts with no PID/TID/Tag and later gets a row with them must
  reflow immediately (the delegate reads the model's getters fresh on every
  paint, so this is automatic — no signal needed — but confirm no stale-width
  caching was hiding elsewhere).
- Multi-source (merged) tabs: if *any* device in a merged view has PID/TID/Tag,
  the segment shows for all rows in that tab (per-tab, not per-source) — rows
  from the silent source just render blank in an otherwise-visible column,
  matching how Time/Level already behave for a raw-fallback row.
- `_PIDTID_MIN_W`/`_TIME_MIN_W` floors still apply once a segment *is* shown —
  only the fully-empty case goes to `0`, not "shrink below the floor."

## Verification

- [x] `uv run pytest tests/test_log_model.py tests/test_log_delegate.py tests/test_models.py`
      (91 passed) + a `-k "wrap or gutter or process_name or process_column or delegate"`
      slice across the suite (29 passed) to cover sizeHint/wrap interaction
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` screenshot (`auto-hide-columns` scenario, before/after): confirms
      no trailing dash, no reserved Tag gap, and the Tag segment reappearing
      retroactively for the whole tab once a row has one

## Open questions

None — scope confirmed with the user: PID·TID and Tag both auto-hide/show;
Process keeps its existing manual toggle.
