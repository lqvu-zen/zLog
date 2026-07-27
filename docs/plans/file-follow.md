# Plan: Follow a log file live (tail -f)

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-24
- **Related:** [large-file-progress.md](large-file-progress.md), [windows-debug-output.md](windows-debug-output.md), [windows-app-focus.md](windows-app-focus.md), [open-in-new-tab.md](open-in-new-tab.md)

## Goal

Point zLog at a log **file** an app writes and watch it live — new lines appear as
they're appended, with the whole query bar, filters, and export working as usual.

## Why

The debug-output and launch sources only catch apps that use
`OutputDebugString` or print to a console. A great many apps (services, servers,
anything with its own logger) write to a file instead — today you can only open
that file as a static snapshot and re-open it to see more. This closes the last
big gap in "debug any app", and unlike the DBWIN work it's **cross-platform**, so
it's fully testable here.

## Scope

- **In:** **File → Follow File…** picks a `.log` (or any text file); zLog loads
  the existing content, then keeps streaming appended lines until Stop. Handles
  the file being truncated or rotated (recreated) underneath. Opens in a tab
  labelled by the file name, reusing the tab rules from `open-in-new-tab.md`.
- **Out (non-goals):** watching a whole directory / glob, remote files (SSH, UNC
  beyond what the OS mounts), and inotify-style OS watch APIs — a small poll is
  simpler, portable, and plenty for log tailing.

## Design

Mirrors `FileLoader` (which already reads a big file off-thread in batches) but
doesn't stop at EOF: it sleeps briefly and checks for growth. Rotation handling is
the only subtle part, and it's pure arithmetic, so it goes in `core/`.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/tailer.py` (new) | core | Pure rotation/truncation logic, no IO: `TailState(offset, size, inode)`; `next_action(prev, cur) -> "read" | "rewind" | "idle"` — if the file shrank, or its identity changed, the writer rotated it, so restart from 0; if it grew, read from `offset`; else idle. Unit-tested with plain tuples. |
| `src/zlog/ui/file_follower.py` (new) | ui | `FileFollower(QThread)` with the reader contract (`batch_ready`, `error`, `stream_ended`): open, read to EOF via the existing `iter_entry_batches`, then loop `sleep(_POLL_INTERVAL)` → `os.stat` → act on `core.tailer.next_action`. Reuses `should_flush`-style batching so a chatty file can't flood the UI. `stop()` clears the flag; the poll sleep bounds the exit latency. |
| `src/zlog/ui/main_window.py` | ui | **File → Follow File…** (`QFileDialog`) → reuse-or-new tab (`_tab_is_reusable`/`_new_tab`) → `capture.attach(sess, FileFollower(path), stream_label=Path(path).name)` → `_set_streaming_controls()`. Stop uses the existing `capture.detach`. Remember recent followed files alongside `_recent`. |
| `docs/GUIDE.md` | — | A "Follow a log file" paragraph next to the Windows section. |
| `tests/test_tailer.py`, `tests/test_file_follower.py` (new) | — | Pure: grow → read, shrink → rewind, same size → idle, identity change → rewind. Live: write a temp file, start the follower, append lines, assert they arrive; truncate and assert it re-reads; `stop()` ends the thread. Cross-platform, so this is genuinely exercised in CI. |

## Architecture touch points

- **Threading:** another `QThread` emitting `batch_ready` — the window never
  touches the file. Attaches through `CaptureController` like every other source,
  so Stop/teardown is already handled.
- **Model/proxy:** none. Rows are `LogEntry` from the existing parser, so a
  logcat-format file gets full fields and any other format falls back to raw text
  in `message` (the parser already guarantees nothing is dropped).
- **Dependency direction:** `core/tailer.py` is IO-free and Qt-free; the thread
  lives in `ui/` beside `file_loader.py`. `ui → core` holds.

## Risks & regressions to check

- **Rotation/truncation:** the common logger behaviour. Shrink or identity change
  must rewind, not silently stop or replay stale bytes.
- **Partial last line:** a writer may flush mid-line; don't emit a truncated entry
  — keep the remainder buffered until the newline arrives.
- **Encoding:** decode with `errors="replace"` like `AdbReader`, never crash.
- **File locked / deleted** while following (common on Windows): report via
  `error` and keep the already-captured lines on screen.
- **Poll cost:** an `os.stat` every ~250 ms is negligible; confirm no busy-wait and
  that `stop()` returns promptly.
- **Huge pre-existing file:** the initial read should reuse the large-file path so
  a 500 MB log doesn't freeze the window before following starts.

## Verification

- [ ] `uv run pytest` (new tailer + follower tests, incl. append/truncate live)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: `Follow File…` a file, append with `echo >>`, see lines arrive;
      truncate it and confirm it re-reads from the start; Stop ends cleanly.

## Open questions

- **Poll interval:** ~~fixed vs. adaptive~~ **Resolved:** fixed 250 ms.
- **Start at end?** ~~EOF or whole file?~~ **Resolved:** load-then-follow.
  `FileFollower(from_end=True)` exists and is tested, but isn't exposed in the UI
  yet — add a checkbox if opening a huge file proves painful.
- **Open Log… checkbox?** **Resolved:** separate menu item; Open stays a snapshot.

## Known limitation

An in-place rewrite that lands on **exactly the same size with the same inode** is
undetectable without hashing the content — `tail -f` has the same blind spot.
Truncation to a different size, and replacement with a new file, are both handled.
