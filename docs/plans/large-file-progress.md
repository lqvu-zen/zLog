# Plan: Large-file open progress

- **Status:** Approved  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Claude
- **Created:** 2026-07-18
- **Related:** save-load.md, open-recent.md, ring-buffer-cap.md

## Goal

Opening a big `.log` streams it in the background with a cancelable progress
dialog and fills the view incrementally, instead of one blocking read that freezes
the window until the whole file is parsed.

## Scope

- **In:** a background file loader for large files that emits parsed batches +
  progress; a modal-but-cancelable `QProgressDialog`; the model fills as batches
  arrive. Small files keep the existing synchronous path.
- **Out (non-goals):** memory-mapping / partial windows into huge files (the
  ring-buffer cap already bounds retained rows); changing the on-disk format.

## Design

`_load_log_file` currently does `open().read()` then `text_to_entries(text)` then
`append_entries` — all on the main thread. Add a `QThread` loader that reads the
file line-by-line in chunks, parses each with the same `parse_line`, and emits
`batch_ready(list[LogEntry])` in `_BATCH_SIZE` chunks plus `progress(read_bytes,
total_bytes)` — mirroring `AdbReader`'s batching + signal-to-UI discipline. The
Qt-free part (turning an iterable of lines into batches) is a small `core` helper
that's unit-testable.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/session.py` | core | Add `iter_entry_batches(lines, size=50) -> Iterator[list[LogEntry]]`: parse `parse_line` per line, yield lists of `size`. Pure, unit-tested; reused by the loader thread. Keep `text_to_entries` for the small-file/synchronous path. |
| `src/zlog/ui/file_loader.py` | ui | New `FileLoader(QThread)`: ctor `(path)`. `run()` opens the file (`utf-8`, `errors="replace"`), iterates lines, batches via `iter_entry_batches`, emits `batch_ready(list[LogEntry])` and `progress(int, int)` (bytes read / total from `os.path.getsize`), then `done(int total_lines)`; `error(str)` on `OSError`. A `stop()` sets `_running = False` so Cancel aborts mid-read (checked each batch). Widgets are never touched — only signals, per the threading rule. |
| `src/zlog/ui/main_window.py` | ui | `_load_log_file`: if `os.path.getsize(path)` exceeds a threshold (e.g. 5 MB), take the async path — stop any live stream, `set_pids(None)`, `model.clear()` + `clear_process_names()`, create a `QProgressDialog` ("Opening <name>…", Cancel), start a `FileLoader`, connect `batch_ready`→`model.append_entries`, `progress`→dialog value, `done`→close dialog + status + `_remember_recent`, `error`→status. Cancel calls `loader.stop()`. Keep a reference to the loader (like `reader`) so it isn't GC'd. Small files keep the current synchronous body. |

## Architecture touch points

- **Threading:** `FileLoader` is a `QThread`; it reaches the UI only via
  `batch_ready`/`progress`/`done`/`error`, delivered on the main thread — the
  single most important rule. The model is appended to only in the slot.
- **Model/proxy:** uses the existing virtualized `append_entries`
  (`beginInsertRows`); no reset per batch.
- **Dependency direction:** `ui.file_loader` → `core.session`/`core.parser`;
  one-way.

## Risks & regressions to check

- Batching preserved (`_BATCH_SIZE` = 50) so a huge file doesn't flood the event
  loop — same rationale as `AdbReader`.
- Cancel mid-load must stop the thread cleanly and leave the partially-loaded
  rows (or clear — decide: keep what's loaded, status "cancelled after N lines").
- Autoscroll/follow while loading: appends during load should respect the
  at-bottom follow rule already in `_on_batch`; route batches through the same
  append path the live stream uses, or a minimal append that doesn't yank scroll.
- A file that's opened, then Open Recent re-opened: ensure only one loader runs
  (stop/replace any in-flight loader, like starting a new stream stops the old).
- Threshold choice: below it, the sync path keeps Open instant for typical files
  (no dialog flicker for small logs).
- `progress` total is bytes; lines-read is unknown up front, so the dialog is
  byte-based (monotonic, accurate) rather than line-count-based.

## Verification

- [ ] `uv run pytest` (unit-test `iter_entry_batches`: batch sizing, remainder,
      empty input; each entry round-trips through `parse_line`).
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` driver scenario `large-file`: point the loader at a temp file of
      N lines (or drive `FileLoader` directly and pump signals), screenshot the
      populated view; the progress dialog itself is timing-dependent, so the
      scenario asserts the rows landed rather than grabbing the transient dialog.

## Open questions

- Threshold value (MB) and whether cancel keeps partial rows. Leaning: 5 MB, keep
  partial with a status note.
