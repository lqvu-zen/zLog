# Plan: Pause / resume the stream

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v1.2 "Capture & scale", [smart-follow.md](smart-follow.md)
  (scroll-up pauses tailing; this is a hard freeze of the whole view)

## Goal

After this ships, a **Pause** button freezes the log view without stopping adb:
capture keeps running, new lines buffer in the background, and **Resume** flushes
them in. Lets the user read a fast-scrolling log with a hard stop, then catch up.

## Why

Smart-follow lets you scroll up without being yanked, but lines still append
below. When a log floods, users want a true "stop the world" to read the current
screen, then resume without having lost anything or having killed the adb stream
(which would drop the on-device position and re-dump the buffer on restart).

## Scope

- **In:** a Pause/Resume button (enabled only while streaming); `on_batch`
  buffers entries while paused; Resume flushes the buffer through the normal
  append path (so ring-buffer cap + follow still apply); Stop resets pause state.
- **Out:** pausing a loaded file (nothing streams), a max buffer cap while paused
  (the ring-buffer cap still bounds things once flushed), keyboard shortcut.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | State `self._paused = False`, `self._pause_buffer: list[LogEntry] = []`. Add `self.pause_btn` ("Pause", disabled) to the stream controls after Stop; connect `clicked → _toggle_pause`. `on_batch`: if paused, extend the buffer + status count and return (no append/scroll). `_toggle_pause`: flip state; pausing sets the label to "Resume"; resuming flushes the buffer via `on_batch(...)` and relabels "Pause". `start()`: enable the button, clear pause state. `stop()`: disable + clear pause state. |
| `tests/test_main_window_settings.py` | tests | While `_paused`, `on_batch` buffers (model unchanged, buffer grows); `_toggle_pause` to resume flushes the buffer into the model and clears it. |

## Architecture touch points

- **Threading:** unchanged — `on_batch` still runs on the main thread from the
  reader signal; pausing only changes whether entries are appended now or buffered.
- **Model virtualized:** resume flushes through `append_entries` (+ cap), so no new
  model path.
- **adb keeps running:** we never touch the reader on pause, so the on-device
  position is preserved and there's no re-dump/duplication.

## Risks & regressions to check

- **Resume ordering:** buffered lines must flush in arrival order, before any newer
  live lines (flush is a single `on_batch` call, then normal flow resumes).
- **Stop while paused:** must clear `_paused`/buffer and re-enable Start cleanly.
- **Follow interaction:** after a resume flush, follow (if on and at bottom) tails
  to the newest — expected.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Screenshot: Pause button present in the stream controls.
