# Plan: Diff two captures

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v2.0 (diff two captures), [save-load.md](save-load.md)

## Goal

After this ships, File → **Diff Against File** compares the current log with another
saved log and shows a unified diff — lines only in the current capture (−), lines
only in the other (+), and common lines — ignoring volatile time/pid so identical
events line up across runs.

## Scope

- **In:** pure diff over normalized line keys (`level/tag: message`); a modal
  results dialog (colored ±/context list) with a +/− count in the title.
- **Out:** true side-by-side two-pane view, word-level intra-line diff, diffing two
  arbitrary files (compares against the *current* view), 3-way diff.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/diff.py` | core | `line_key(entry)` → `"{level}/{tag}: {message}"` (ignores time/pid). `diff_logs(a, b)` → `list[tuple[str, str]]` of (op, line) where op ∈ {" ","-","+"}, via `difflib.SequenceMatcher` opcodes (replace → delete then insert). Pure. |
| `src/zlog/ui/main_window.py` | ui | Import the diff fns + `QColor`. File → **Diff Against File…** picks a `.log`, reads it, builds keys from `model.all_entries()` and `text_to_entries(other)`, runs `diff_logs`, and shows a modal `QListWidget` (monospace; − red, + green, context muted) titled with the ±counts. |
| `tests/test_diff.py` | tests | `line_key` ignores time/pid; `diff_logs` marks equal/delete/insert/replace correctly; identical inputs are all context. |

## Architecture touch points

- **Pure/tested diff** in core (stdlib `difflib`); the UI only reads a file and
  renders. Reuses `text_to_entries`.
- **Normalized keys** so timestamps/pids don't make every line "changed."

## Risks & regressions to check

- **Large diffs:** on-demand only; the list is built once. Big captures produce big
  lists — acceptable for a diff view.
- **Empty current/other:** all-insert / all-delete respectively, no crash.
- **Unreadable file:** report and abort.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: open a log, Diff Against a slightly different one; ± lines are colored.
