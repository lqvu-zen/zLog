# Plan: Normalize line endings with .gitattributes

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-01
- **Related:** [ci-windows-job.md](ci-windows-job.md), [release-workflow.md](release-workflow.md)

## Goal

A checkout on Windows and a checkout on Linux produce the **same** bytes in git,
so `git status` stops claiming every file changed when nothing did.

## Why

The repo has **no `.gitattributes`**. Observed in this working tree:

```
122 files changed, 8143 insertions(+), 8143 deletions(-)
git diff --ignore-cr-at-eol   → empty
```

Every line of the repo "changed" and not one character differed. That's not
cosmetic:

- It **hides real diffs**. A one-line fix is invisible in an 8,000-line diff, so
  review degrades to trusting the author.
- It risks **committing whole-file churn**, which then poisons `git blame` and
  makes every future bisect harder.
- It will **break the Windows CI job** ([ci-windows-job.md](ci-windows-job.md)):
  `ruff format --check` on a CRLF checkout can fail for line-ending reasons alone,
  producing a red build with no real defect behind it.

Cost to fix: one file. This is the highest value-per-minute item in the audit,
and it's a prerequisite for the highest-value one.

## Scope

- **In:** a `.gitattributes` declaring text normalization and the handful of
  binary/exempt paths; a one-time renormalize commit; a note in `CLAUDE.md`.
- **Out (non-goals):** changing anyone's editor config, adding `.editorconfig`
  (worth doing, separate purpose), rewriting history to remove past churn, and
  enforcing endings via a pre-commit hook.

## Design

Let git normalize to LF in the repository and check out natively; declare the
exceptions explicitly rather than relying on git's content heuristics.

| File | Change |
|---|---|
| `.gitattributes` (new) | `* text=auto eol=lf` as the default. Explicit `text` for `*.py *.md *.toml *.yml *.json *.qss`. Explicit `binary` for `*.png *.ico *.zip *.exe`. `*.bat text eol=crlf` — a batch file with LF endings can misbehave under `cmd.exe`, and `build.bat` is a shipped entry point. |
| one-time commit | `git add --renormalize .` in its own commit, touching nothing else, with a message saying it is pure normalization so future `git blame`/`bisect` readers can skip it. |
| `CLAUDE.md` | One line under "Environment notes": endings are normalized by `.gitattributes`; don't fight it with editor settings. |

## Architecture touch points

- **Threading / model / dependency direction:** none. No application code changes.

## Risks & regressions to check

- **The renormalize commit is large by nature.** Keep it *alone* on the branch so
  it's obviously mechanical; never mix it with a real change.
- **`build.bat` must stay CRLF.** It's the double-click build path; verify it
  still runs after the change rather than assuming.
- **Binary files must not be normalized.** Corrupting a `.png` or the `.ico` this
  way is silent until someone looks at the icon — check the `docs/` screenshots
  and any packaging assets survive.
- **In-flight branches will conflict** after renormalization. There's only this
  line of work right now, so the window is good — do it before starting anything
  branched.
- **`uv.lock`** should be treated as text and normalized like everything else;
  confirm `uv sync` is still happy afterwards.

## Verification

- [ ] After the renormalize commit, a fresh clone on Windows shows a **clean**
      `git status`.
- [ ] `git diff --stat` between before/after (ignoring the renormalize commit)
      shows no content change: `git diff --ignore-cr-at-eol` is empty.
- [ ] `build.bat` still runs from Explorer (CRLF preserved).
- [ ] Screenshots in `docs/` still render; `.ico` still valid.
- [ ] `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`
      all clean. Note: local runs here are **chunked** across processes — CI's
      single-process `uv run pytest -q` remains the authoritative full-suite gate.

## Open questions

- **`eol=lf` vs. `eol=native` for the default?** `lf` is the safer default: it
  makes the *repository* content deterministic regardless of who commits. Windows
  editors handle LF fine today. Leaning `lf`.
- Worth adding `.editorconfig` at the same time? Related but a different purpose —
  separate plan if wanted.
