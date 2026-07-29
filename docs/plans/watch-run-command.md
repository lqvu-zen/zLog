# Plan: Watch action — run a command

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-24
- **Related:** [watch-pattern.md](watch-pattern.md), [windows-app-focus.md](windows-app-focus.md)

## Goal

When a watch pattern matches, optionally **run a command** — not just beep or
notify — so a crash or error line can trigger a screenshot, a bug report, a
webhook, or any script you like.

## Scope

- **In:** an optional command on the watch config; run it when a watch hits,
  detached and non-blocking, with the matched line available via placeholders;
  throttled like the existing notification.
- **Out (non-goals):** a scripting language, chaining multiple commands, capturing
  the command's output into the log (it's fire-and-forget), and running anything
  automatically without the user having typed it.

## Design

The watch feature already detects hits and throttles notifications
(`_watch_hits`, `_notify_watch`, `_watch_last`). This adds one more action at that
same point. The only real design work is doing it **safely**.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/watch_action.py` (new) | core | Pure: `expand_command(template, entry) -> list[str]` — substitutes `{message}`, `{tag}`, `{pid}`, `{level}`, `{time}` into an argv **list** (parsed with `shlex`, never a shell string), so a log line containing `;` or `&&` can't inject anything. Unknown placeholders are left literal. Unit-tested, including injection attempts. |
| `src/zlog/ui/main_window.py` | ui | On a watch hit, if a command is configured and the throttle allows, `subprocess.Popen(expand_command(...))` detached (no pipes, no wait) inside a try/except that reports failures to the status bar. Persist the template via the existing `_settings_specs` table beside the watch pattern. |
| `src/zlog/ui/settings_dialog.py` (or the watch dialog) | ui | A "Run command" field next to the existing sound/notify options, with a short hint listing the placeholders and a note that it runs **without a shell**. |
| `docs/GUIDE.md` | — | Document the placeholders and the no-shell rule. |
| `tests/test_watch_action.py` (new) | — | Placeholder expansion, quoting, a message containing shell metacharacters stays one argument, unknown placeholder untouched, empty template → no command. |

## Architecture touch points

- **Threading:** `Popen` without `wait()` returns immediately, so the UI thread
  isn't blocked; nothing is read back, so no reader thread is needed. Reap
  finished children (or `start_new_session`) so they don't linger as zombies.
- **Model/proxy:** none.
- **Dependency direction:** expansion is Qt-free in `core/`; the window launches.

## Risks & regressions to check

- **Command injection is the whole risk.** A log line is untrusted input. Never
  build a shell string, never pass `shell=True` — argv list only. The tests must
  include a message like `x"; rm -rf ~; echo "` and prove it stays one argument.
- **Runaway launches:** a matching pattern on a chatty log could spawn hundreds of
  processes. Reuse (and probably lengthen) the existing throttle, and consider a
  hard "at most one running at a time" rule.
- **Bad command** (not found, non-zero exit) must report once, not per line, and
  must never raise into the batch handler — a dead reader thread would follow.
- **Blocking:** a command that reads stdin or runs forever must not stall zLog —
  detached, no pipes.
- Interaction with the existing beep/notify actions (all three can be on).

## Verification

- [x] `uv run pytest` (expansion + injection-resistance tests)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: set a watch on a common word with a command that appends to a file;
      confirm it runs, is throttled, and that a line with `;` and quotes in it
      doesn't execute anything extra.

## Resolved

- **Throttle:** separate and longer — 10s for the command vs. 3s for the
  notification, since spawning a process is heavier than a beep.
- **Confirmation:** `WatchDialog` + a `QMessageBox.question` in
  `_set_watch_dialog` confirm whenever the command text changes to something
  new (not just once ever) — cheap and catches edits, not only first-time setup.
- **`{line}`:** added alongside `{message}`/`{tag}`/`{pid}`/`{level}`/`{time}`.

## Implementation notes

- `core/watch_action.expand_command` splits the **template** with `shlex`
  (matching `launcher.build_argv`'s `posix=(os.name != "nt")` convention) before
  substituting placeholders into the resulting argv slots — so untrusted log
  content never re-enters argv splitting and can't inject an argument or
  metacharacter.
- `ui/watch_dialog.WatchDialog` replaces the old single-field `QInputDialog`.
- Settings gained a `watch_command` key alongside `watch`; `_apply_watch` takes
  an optional `command` (default `None` = leave unchanged) so the settings
  loader for `watch` doesn't clobber a separately-loaded `watch_command`.
