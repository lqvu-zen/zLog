# Plan: Follow a folder (newest file matching a glob)

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
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
| `src/zlog/core/dirfollow.py` (new) | core | `pick_newest(dir_path, pattern) -> str \| None` (mtime, tie-break on lexicographically largest name) and `should_switch(old_file_stable_for, threshold) -> bool`. Both pure, both unit-tested. |
| `src/zlog/ui/dir_follower.py` (new) | ui | **`DirFollower(QThread)` reimplements the read/poll loop directly rather than wrapping an inner `FileFollower` instance**, as the sketch proposed — see Architecture touch points for why (a real, non-obvious threading hazard the sketch would have hit). Reuses `FileFollower`'s pure helpers (`file_key`, `should_flush`) and `core.tailer`'s (`TailState`, `next_action`, `split_complete_lines`) rather than duplicating that logic. |
| `src/zlog/ui/main_window.py` | ui | `follow_folder()` (parallel to `follow_file()`) + `_on_dir_follower_switched(name)` (the status-bar note on swap). |
| `src/zlog/ui/menus.py` | ui | New File-menu action next to "&Follow File…". |
| `src/zlog/core/tabstate.py` / `src/zlog/core/settings.py` | core | **Not changed — the sketch's premise was wrong.** `_tab_states()` (`main_window.py:2586`) only persists `sess.file_path` **when `sess.reader is None`** — i.e. a live `FileFollower` tab is *already* excluded from restore today ("a live capture isn't restorable," `tabstate.py:19`); only a static `Open Log` reopen is remembered. A directory-follow is equally a live capture, so it correctly needs no new persistence to match existing behavior, not new code to add some. |
| `tests/test_dirfollow.py`, `tests/test_dir_follower.py` (new) | — | `pick_newest`/`should_switch` (pure); `DirFollower` against real files — initial read, growth, swap after the grace period, old-file writes after a swap don't reappear, no-match error, stop — plus window wiring (`follow_folder()`, cancel, no-match, the switch status note). |

## Architecture touch points

- **Threading:** **the sketch's "wrap an inner `FileFollower`" shape doesn't
  work, and it's worth recording why.** A `FileFollower` constructed inside
  `DirFollower.run()` gets QObject thread-affinity = `DirFollower`'s own
  thread (affinity is set at construction, not by which thread later calls
  `.start()` on it). Its `batch_ready`/etc. signals, connected to
  `DirFollower`'s own signals, would then cross from the inner reader's
  actual OS thread back to `DirFollower`'s affinity thread as a **queued**
  connection (Qt's `AutoConnection` rule for cross-thread emission) — but
  `DirFollower.run()` is a plain `while` loop, not `self.exec()`, so nothing
  on that thread ever pumps a `QEventLoop` to deliver the queued call. The
  batches would simply never arrive. `DirFollower` reimplements the loop
  directly instead, so its signals emit from the same thread they're defined
  on and connect straight to `MainWindow` (which does run the app's event
  loop) — the same shape every other reader already uses.
- **Model/proxy:** none.
- **Dependency direction:** `core/dirfollow.py` stays pure; the loop
  reimplementation is `ui`-only.

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

- [x] `uv run pytest` — `tests/test_dirfollow.py` (`pick_newest`/`should_switch`
      pure cases) and `tests/test_dir_follower.py` (real threads, real temp
      files: initial read + follow, swap-to-newer-file after the grace period
      with the old file's post-swap writes confirmed absent, no-match error,
      prompt stop, window wiring) — all green.
- [x] `uv run ruff check .` / `ruff format --check .` clean.
- [x] Manual (`run-zlog` `follow-folder` scenario, screenshotted): a real
      `DirFollower` against a temp directory streams a sample file's lines
      into a tab correctly.
- [x] Covered by `test_swaps_to_a_newer_file_after_it_stabilizes`: writing to
      `app-1.log` after the swap to `app-2.log` is confirmed **not** to
      reappear in the captured batch — the exact "switch, then confirm no
      lost/duplicated lines" scenario this item asked for, done as an
      automated test against real files rather than only by hand.
- [x] Covered by the same test and by `should_switch`'s unit tests: the grace
      period (`_SWITCH_GRACE = 2 * _POLL_INTERVAL` = 0.5s, per the Open
      Questions lean below) is exercised for real, not just asserted in
      isolation.

## Open questions

- **Switch instantly, or after an idle grace period on the old file?**
  **Resolved: grace period**, as leaned — `_SWITCH_GRACE = 2 * _POLL_INTERVAL`
  (0.5s) in `ui/dir_follower.py`. Revisit the exact multiplier if real-world
  rotation scripts turn out to pause longer than that between files.
- **What if two files share the same newest mtime** (second-resolution
  filesystems, bulk copy)? **Resolved: tie-break on the lexicographically
  largest name**, as leaned — implemented in `pick_newest` via `max()` over
  `(mtime, basename, path)` tuples, covered by
  `test_tie_breaks_on_lexicographically_largest_name`.
