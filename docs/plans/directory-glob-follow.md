# Plan: Follow a folder (newest file matching a glob)

- **Status:** Approved  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-20
- **Related:** [file-follow.md](file-follow.md)

## Goal

"Always follow the newest file matching `app-*.log`" — for apps that rotate logs
by filename (a fresh file per run/day) rather than by inode, which
[file-follow.md](file-follow.md) already handles for a single fixed path.

## Scope

- **In:** watch a directory + glob pattern; when a newer matching file appears,
  cleanly stop following the old one and start following the new one from its
  start; a "Follow &Folder…" File-menu action + dialog (folder picker, pattern
  field, default `*.log`); a status note on switch-over ("switched to newest
  file: app-2.log") so a swap is never mistaken for data loss.
- **Out (non-goals):** merging several simultaneously-growing files in the
  folder into one tab (that's the existing multi-source shape from
  [merged-multi-device.md](merged-multi-device.md), not revisited here — this
  plan follows exactly one file at a time, "the newest one"); reacting to the
  folder itself being deleted/recreated as a distinct signal.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/dirfollow.py` (new) | core | `pick_newest(dir_path: str, pattern: str) -> str \| None`: pure glob + mtime pick, unit-testable without threads. Also a `should_switch(current_mtime_age, threshold)`-shaped helper for the grace-period decision (see Risks) — pure, testable. |
| `src/zlog/ui/dir_follower.py` (new) | ui | A `QThread` orchestrating swap-over: polls `pick_newest` on the same cadence as `FileFollower._POLL_INTERVAL`, and when the newest path changes, stops its inner `FileFollower` and starts a new one (`from_end=False`, so nothing in the new file is missed) against the new path. Relays the inner reader's `batch_ready`/`error`/`stream_ended` signals unchanged, so it drops into `CaptureController.attach` exactly like `FileFollower` does today. |
| `src/zlog/ui/main_window.py` | ui | `follow_folder()` slot, parallel to `follow_file()` (`main_window.py:3446` area) — same `clear_on_start`/format-detect/`capture.attach` shape. |
| `src/zlog/ui/menus.py` | ui | New File-menu action next to "&Follow File…". |
| `src/zlog/core/tabstate.py` / `src/zlog/core/settings.py` | core | Persist folder + pattern for tab restore, mirroring how a followed file's path is remembered today. |
| `tests/test_dirfollow.py` (new) | — | `pick_newest`: empty dir, one match, several matches, "newest changes when a new file lands," pattern excludes non-matching names. |

## Architecture touch points

- **Threading:** the swap-over logic runs on the wrapper thread; tearing down
  the old `FileFollower` and starting a new one must happen entirely off the UI
  thread, reaching it only through the relayed signals — same contract as every
  other reader.
- **Model/proxy:** none.
- **Dependency direction:** `core/dirfollow.py` is pure; the thread orchestration
  is `ui`-only (it directly constructs a `FileFollower`, so it can't live in
  `core`).

## Risks & regressions to check

- **The swap boundary must be unambiguous to the user.** The new file is read
  from its own start — it is a different file, not a continuation — but that
  must be visible in the UI (a status message), or a swap reads exactly like a
  silent gap in the stream.
- **"Newest" by mtime is fooled by clock skew or a bulk copy that preserves old
  timestamps** — document as a known limitation, the same class of caveat
  `FileFollower`'s own docstring already calls out for in-place rewrites
  (`ui/file_follower.py:1-11`).
- **Swap-too-early risk:** a rotation script may `touch`/create the new file
  slightly before the app starts writing to it. Switching the instant a newer
  file appears could follow an empty file while the old one still has trailing
  lines. **Recommendation: require the old file to have stopped growing for a
  short grace period before switching** — needs a deliberate design (see Open
  questions), not a default discovered as a bug later.
- **Polling a directory listing every cycle must stay cheap** even with many
  files present — glob cost, not file-read cost, so this should be fine, but
  worth confirming against a folder with thousands of rotated files.

## Verification

- [ ] `uv run pytest` (`pick_newest` cases above)
- [ ] `uv run ruff check .` / `ruff format --check .`
- [ ] Manual: write to `app-1.log`, then create and write to `app-2.log` while
      following the folder — confirm the switch, the status note, and that
      `app-1.log`'s last lines aren't lost.
- [ ] Manual: the grace-period decision (once made) exercised with a file
      created-then-immediately-superseded, to confirm it doesn't false-swap.

## Open questions

- **Switch instantly, or after an idle grace period on the old file?**
  Leaning grace period (e.g. no growth for 2× the poll interval) — needs a
  concrete number chosen deliberately, not guessed.
- **What if two files share the same newest mtime** (second-resolution
  filesystems, bulk copy)? Tie-break needs a rule (e.g. lexicographically
  largest name) rather than being left to whatever `glob` happens to return.
