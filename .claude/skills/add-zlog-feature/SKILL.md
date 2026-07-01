---
name: add-zlog-feature
description: 'Add a new feature to the zLog desktop app the right way — end to end, following the project''s own conventions. Use this whenever the user asks to add, build, implement, or wire up any new capability in zLog: a new toolbar control, filter, column, dialog, a device picker, package/PID filter, save/load of logs, regex search, theming, a change to how adb is invoked or how the log stream is read, autoscroll behavior, or anything that means editing files under `src/zlog/`. Trigger even when the user just describes the behavior they want ("let me pick which device", "only show my app''s logs", "let me save the current log to a file", "highlight a tag") without saying the words "feature" or "implement". This skill carries zLog''s layered architecture rules, the Qt threading model, the plan-first design→implement→test→review→commit workflow, and the exact verification commands, so you don''t reinvent them each time. Do NOT use it for pure UI/UX design reviews (use review-zlog-ui) or for just launching/screenshotting the app (use run-zlog).'
---

# Adding a feature to zLog

zLog is a **PySide6 (Qt) desktop app** for viewing Android `adb logcat`, managed
with **uv**. All code lives in the `src/zlog/` package; the entry point is
`zlog.app:main`, exposed as the `zlog` console-script and via `python -m zlog`.

The point of this skill is that adding a feature here is not just "write the code."
A change that ignores the app's threading model or its one-way layer dependencies
will look correct and still freeze the UI under load or create import cycles. So
the workflow below is **plan-first**: you capture an approved written plan in
`docs/plans/` before touching code, then implement it, then verify for real —
tests passing and the app actually rendering — before anything is committed.

Work through the phases in order. Don't skip the planning or the test/review phase;
a feature that isn't planned and verified isn't done.

## Where things live

| Concern | File |
|---|---|
| `LogEntry`, `LEVEL_RANK`, severity `rank` | `src/zlog/core/models.py` |
| logcat line parsing (`parse_line`) | `src/zlog/core/parser.py` |
| `adb logcat` streaming thread (`AdbReader`) | `src/zlog/adb/reader.py` |
| Qt table model, filter proxy | `src/zlog/ui/log_model.py` |
| color themes (Light/Dark) + palette tokens | `src/zlog/ui/theme.py` |
| main window, toolbar, wiring | `src/zlog/ui/main_window.py` |
| `QApplication` bootstrap (`main`) | `src/zlog/app.py` |
| `__version__` | `src/zlog/__init__.py` |
| deps, scripts, tooling config | `pyproject.toml` |
| unit tests | `tests/` |
| **plans (write one before coding)** | `docs/plans/` |

See `docs/ARCHITECTURE.md` for the reasoning and an extension-points table that
says where common features belong, and `docs/plans/README.md` for the plan-first
convention.

## Architecture rules that always apply

These are the invariants that make zLog work. Most "looked fine, broke in practice"
bugs come from violating one, so internalize the *why*, not just the rule.

- **Plan first.** No code changes without an approved plan in `docs/plans/` (see
  phase 3). This is a hard rule, not a suggestion.

- **PySide6 (Qt) only for the UI.** Build from `QtWidgets`. Don't pull in Tkinter,
  a web stack, or a second GUI toolkit.

- **Worker threads never touch widgets directly.** Anything long-running (reading a
  stream, scanning a file, running an `adb` command) belongs on a `QThread`. Qt
  widgets are **not** thread-safe, so a worker that updates a model or widget from
  its own thread will eventually crash or corrupt the display. Workers communicate
  with the UI in exactly one way: by **emitting a signal** that a main-thread slot
  handles (see `AdbReader.batch_ready` / `error` → `MainWindow.on_batch` /
  `on_error`). Any new background work must follow the same path. This is the
  single most important code rule.

- **`core/` stays Qt-free.** `core/models.py` and `core/parser.py` import no Qt.
  New logic that doesn't need a `QObject` — parsing, format detection, a
  PID→process-name map, a serializer — goes in `core/` so it stays unit-testable
  without a display. Never add `from PySide6 ...` under `core/`.

- **Dependency direction is one-way: `ui` → `adb` → `core`.** `ui` may import from
  `adb` and `core`; `adb` may import from `core`; `core` imports neither. The
  reverse must never happen. Crossing this line creates import cycles and couples
  the data layer to the widgets.

- **Keep the model virtualized; never build a widget per row.** Rows live in
  `LogTableModel`'s list and `QTableView` renders only the visible ones. Add rows
  with `append_entries` (which wraps `beginInsertRows`/`endInsertRows`); never call
  `beginResetModel` just to append, and never materialize rows into widgets. A
  feature that adds a column extends `COLUMNS` + `data()` + `headerData()`, not the
  view.

- **Filter through the proxy, not the master list.** Visibility rules (level, text,
  and future ones like package or regex) belong in `LogFilterProxy.filterAcceptsRow`
  via `invalidateFilter()`. Keep the master list (`_rows`) complete so clearing a
  filter is instant — don't drop entries from the model to filter.

- **Preserve reader→UI batching.** `AdbReader` emits ~`_BATCH_SIZE` (50) entries
  per signal so a busy log doesn't flood the event loop. If you change the read
  loop, keep batching.

- **Route colors through `ui/theme.py`.** All palette tokens live there (per-level
  row tints, chrome colors, the regex-error tint) and the model gets its tints from
  the active theme. Add a new color to a `Theme` rather than hard-coding a hex value
  at a widget.

- **Comments explain WHY, not WHAT.** Add one only when a line's reason is
  non-obvious.

- **Version bumps happen only on release.** Don't change `__version__`
  (`src/zlog/__init__.py`) or `pyproject.toml`'s `version` for individual features
  or fixes — bump them only when cutting a release.

## The workflow

### 1. Understand the request

Restate it in one sentence: what should the user be able to do after this ships
that they can't now? If a real ambiguity blocks the design (e.g. "filter by app" —
by package name or by PID? persist the choice or not?), ask **one** focused
question before planning. Don't ask about things you can reasonably default.

### 2. Locate the code

Find the area you'll change with targeted Grep inside `src/zlog/`, then Read the
relevant sections — not the whole repo:

```
Grep pattern="<relevant keyword>" path="src/zlog" output_mode="content" -n=true
```

Read the few functions you'll touch plus their direct callers/callees. Check the
extension-points table in `docs/ARCHITECTURE.md` — it usually names the right layer.
While you're in there, check whether part of what's asked **already exists** (a
`rank` on `LogEntry`, a filter hook on the proxy) so you extend rather than
duplicate.

### 3. Write the plan — in `docs/plans/` — and get it approved

This is the gate. **Do not edit code until a plan exists in `docs/plans/` and the
user has approved it.**

- Copy `docs/plans/TEMPLATE.md` to `docs/plans/<short-slug>.md` (e.g.
  `device-picker.md`). **One plan per purpose** — if the request is large, split it
  into several focused plan files rather than one sprawling document, and
  cross-link them in their `Related` lines.
- Fill in the template: **Goal** (one sentence), **Scope** (in / non-goals),
  **Design** (the files and the layer each belongs to; functions/classes added or
  changed), **Architecture touch points** (threading + the signal used to reach the
  UI; model/proxy changes — a new column is `COLUMNS` + `data` + `headerData`, a new
  filter is `filterAcceptsRow` + a setter calling `invalidateFilter`; confirm the
  `ui → adb → core` direction holds), **Risks & regressions**, **Verification**, and
  any **Open questions**.
- Aim for the smallest change that fully satisfies the request and respects the
  rules. Resist scope creep and incidental refactors.
- Add a row for the plan in `docs/plans/README.md` and set its **Status: Draft**.
- For a substantial or risky feature, getting independent eyes on the plan pays off:
  if subagents are available, have a fresh agent sanity-check it — a fresh agent has
  no anchoring from this conversation and will catch absorbed assumptions.
- Show the plan to the user. Once they're on board (a "go ahead" with no comment
  counts as approval), set the plan's **Status: Approved**. Use a task list so the
  concrete changes are visible as you work.

### 4. Implement

Set the plan's **Status: In progress**. Edit only inside `src/zlog/` (and `tests/`
when the feature adds testable logic). Don't touch `pyproject.toml` except for a genuinely required new dependency
(versions change only at release, not here). Follow the approved plan; if
reality forces a deviation, update the plan file rather than silently diverging.
(Don't touch `__version__` or `pyproject.toml`'s `version` — those change only at
release time, not per feature.) Keep `core/` Qt-free and keep all background work
behind signals.

### 5. Test and smoke-check — not optional

Run the unit suite and fix anything red:

```bash
cd D:/Projects/zLog && uv run pytest -q
```

**Add a test when the feature adds testable non-UI logic** — a new parser case, a
filter predicate, a serializer. Put it in `tests/` in the style of
`tests/test_parser.py`. Filter logic is testable without Qt if you keep the
predicate as a pure function in `core/` and have the proxy call it; prefer that
shape so it can be covered. A pure-UI change (a button, a dialog) usually has
nothing unit-testable — verify it by reasoning about the widget code and by
screenshot.

Then confirm it renders and nothing regressed. With a display:

```bash
cd D:/Projects/zLog && uv run zlog
```

Headless (renders the window to a PNG via `widget.grab()`, no physical display):

```bash
cd D:/Projects/zLog && uv run --with pillow python .claude/skills/run-zlog/scripts/driver.py smoke
```

Read the resulting screenshot in `.claude/skills/run-zlog/screenshots/`. If the
feature reaches a new UI state, add or extend a scenario in the driver (see the
`run-zlog` skill) so it's captured. Tick the plan's **Verification** checkboxes as
you go. If neither a display nor the headless driver is available, say so plainly
and lean on the unit tests.

Lint and format before review:

```bash
cd D:/Projects/zLog && uv run ruff check . && uv run ruff format .
```

If a test or the app fails, read the traceback, fix, re-run — loop until clean. A
green claim you didn't actually verify is worse than no claim.

### 6. Review before commit

Run `git diff` and read your change as if reviewing someone else's PR, against the
plan and the architecture rules:

- Does the diff match the approved plan? (If it drifted, the plan should have been
  updated.)
- Any worker thread reaching a widget/model without going through a signal?
- Any `core` or `adb` module importing from `ui` (wrong-way dependency)?
- A new Qt import sneaked into `core/`?
- A full model reset where an in-place `append_entries` belongs?
- Filtering done by mutating `_rows` instead of the proxy?
- No stray version bump (versions change only at release)?

For a non-trivial diff, a fresh-eyes pass pays off; if subagents are available, hand
the diff to one for independent review and fix real issues before committing. Don't
gold-plate small changes.

### 7. Commit

Set the plan's **Status: Done** and tick its remaining boxes. Match the existing
commit style (`git log --oneline -5`). Commit the plan file alongside the code so
the rationale travels with the change. Stage only relevant files — never `.venv/`,
`dist/`, `build/`, `__pycache__/`, or screenshots.

```bash
cd D:/Projects/zLog && git add src/zlog/ docs/plans/<slug>.md docs/plans/README.md <other touched files> && git commit -m "$(cat <<'EOF'
<short description of the feature>

<optional detail line>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### 8. Report back

Tell the user briefly: what was added and where it appears in the UI, which files
under `src/zlog/` changed, the plan file it followed, and any
known limitation or follow-up worth doing next.
