---
name: qa-zlog
description: 'Run zLog''s full test suite and lint as a standalone quality check, on demand — not tied to any feature or release. Use this whenever the user wants a full sanity check of the whole repo: "run the full test suite", "make sure everything still passes", "do a QA pass", "run all the tests", "sanity check the repo", or after a chunk of unrelated work when nothing specific to test comes to mind. This is the single-process, CI-parity run (`uv run pytest -q`) plus `ruff check`/`ruff format --check` — the same commands release-zlog''s gate now just checks via CI instead of re-running. Do NOT use it mid-feature (targeted tests only there — see add-zlog-feature) or as part of cutting a release (release-zlog checks CI instead).'
---

# QA pass for zLog

A full local test run, decoupled from any specific feature or release. Use
this whenever you want to know "is the whole repo actually green right now,"
independent of what CI last reported or what a single change touched.

## Why this is its own thing

Per-feature work runs **targeted** tests only (the files touched, plus close
neighbors) — the full suite is slow enough (routinely several minutes,
sometimes past a 10-minute foreground command, needing to background) that
running it after every change would dominate the session instead of the work.
`release-zlog` doesn't run it either — a release gates on CI, which already
ran the full suite on every commit going in. This skill is where "run
everything, right now, on purpose" lives, callable any time nothing else asks
for it: after a batch of changes, when CI itself looks suspect, when you just
want to be sure before doing something risky, or on a plain "run the full
test suite" request.

No plan doc is written for a QA pass — this is meant to be light-touch and
frequent, not a whole planning cycle. Just run it and report the result.

## The commands

```bash
cd D:/Projects/zLog
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

`pytest -q` in one process is CI's actual command (`addopts = "-p no:randomly"`
in `pyproject.toml` keeps this run in fixed order; CI's separate `shuffled` job
covers order-dependence, not this one). Prefer running it in the background if
it's likely to exceed the tool's foreground timeout — it usually does on this
repo — rather than shortening or chunking it, since the CI-parity claim
depends on it being one process, one full run.

## Reading the result

- **All dots, exit 0:** green. A trailing `Windows fatal exception: access
  violation` block after `[100%]`, naming `conftest.py`'s
  `pytest_sessionfinish` in the trace, is a known, harmless Qt-shutdown
  artifact (that hook calls `os._exit()` on win32) — it is not a failure and
  does not affect the exit code. Don't report it as a problem; do check the
  exit code actually was 0, not just that the trace looks like this one.
- **`F` in the dots / a `FAILED` summary:** real test failures — report them
  plainly, don't paper over or re-run hoping for a different result.
- **A bare exit code with no dots reaching 100% and no `FAILED`/traceback**
  (e.g. a background run that stops mid-suite with an unfamiliar exit code):
  treat as inconclusive, not as a failure — something interrupted the run
  itself rather than a test failing. Re-run before reporting anything either
  way; don't guess at what an unexplained exit code means.
- **Ruff failures** are ordinary lint/format findings — fix them (or run
  `uv run ruff format .` for formatting) the same as any other lint failure.

## Scope

This skill only runs the checks and reports the outcome. Fixing whatever it
finds is a normal follow-up (targeted tests + a real commit), not something
this skill does automatically — don't silently patch things while "just
running QA."
