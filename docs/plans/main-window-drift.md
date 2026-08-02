# Plan: Stop main_window.py regrowing

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-01
- **Related:** [main-window-split.md](main-window-split.md), [tech-debt-refactor.md](tech-debt-refactor.md), [architecture-doc-refresh.md](architecture-doc-refresh.md)

## Goal

`main_window.py` stops growing with every feature — because new UI work has an
obvious home that isn't `MainWindow`, not because we periodically carve it up.

## Why — the last refactor eroded in about a week

```
3,599  before the main-window-split refactor
3,050  after it            (−15%)
3,445  at v1.1.0
3,581  now (234 methods)   (+17% since the refactor, ~7 features)
```

The refactor **worked**. `build.py`, `menus.py`, and `capture_controller.py` are
healthy, well-scoped, and still doing their jobs. Then Event Log, theme editor,
PDF export, adb fetch, and the app-filter merge each added their handlers to
`MainWindow`, and the file is back where it started.

The lesson isn't "refactor harder". A second big carve-up would erode the same
way in the same time, because nothing in the process says where a new action
*should* go. **The missing artifact is a convention, not another extraction.**

Concretely, the file is hard to work in now: 234 methods means finding the handler
for a menu item is a search, not a scroll, and `_settings_specs` alone is ~296
lines. It's also the file most likely to produce a merge conflict, which matters
more as work parallelizes.

## Scope

- **In:** a written rule in `CLAUDE.md` about where new UI code goes; extraction
  of the **two fattest clusters** as worked examples of that rule; a size
  observation (not a hard gate) so drift is visible.
- **Out (non-goals):** another full carve-up of `MainWindow`, splitting
  `_settings_specs` (see below — it's fine), introducing an MVP/MVVM framework,
  a CI line-count failure gate, and any behaviour change whatsoever.

## Design

Convention first, then two extractions that demonstrate it. Deliberately modest:
a change that survives the next five features beats one that halves the file and
erodes again.

**The rule** (to `CLAUDE.md`, under "Architecture rules that always apply"):

> **A new dialog, menu action, or feature flow gets its own `ui/` module.**
> `MainWindow` wires it up — constructs it, connects signals — and holds no more
> than a thin slot. If you're adding more than ~30 lines of logic to
> `main_window.py`, that logic belongs in a new file.

That's testable by a reviewer in seconds, which is what makes it stick.

**The two extractions** — chosen because they're self-contained, already have
tests, and are the largest coherent clusters:

| New file | Moves out of `main_window.py` |
|---|---|
| `src/zlog/ui/export_actions.py` | Save/export flows (CSV/JSON/HTML/PDF, session bundles, redaction hookup). A cohesive group with one shared shape: gather rows → pick a path → write. Takes the model/proxy and a parent widget; returns nothing to the window. |
| `src/zlog/ui/adb_setup_flow.py` | The adb resolution/prompt/fetch orchestration (`_maybe_offer_adb_setup`, fetcher lifecycle, post-fetch re-resolve + refresh). Newest code, cleanest seam, already covered by `test_adb_setup_prompt.py`. |

`MainWindow` keeps the wiring and the signal connections. Nothing moves to `core/`
— this is all Qt.

**What stays put, deliberately:** `_settings_specs` is long but is a *single
source of truth* for save/restore. Splitting it would trade 296 readable lines for
a real risk of a setting silently not persisting. Length is not the same as debt.

| File | Change |
|---|---|
| `CLAUDE.md` | The rule above, plus a line in "Where things live" for each new module. |
| `src/zlog/ui/export_actions.py` (new) | As above. |
| `src/zlog/ui/adb_setup_flow.py` (new) | As above. |
| `src/zlog/ui/main_window.py` | Delegate; delete the moved bodies. No behaviour change. |
| `.claude/skills/add-zlog-feature` | Mention the rule so the workflow enforces it at the point of writing, not at review. |

## Architecture touch points

- **Threading:** unchanged — `AdbFetcher` keeps its `QThread` + signal contract;
  it just gets owned by the flow object instead of the window.
- **Model/proxy:** unchanged. Export reads through the proxy exactly as now.
- **Dependency direction:** new modules live in `ui/` and may import `core/`;
  neither may import `main_window` (that would recreate the coupling). Pass what
  they need as arguments.

## Risks & regressions to check

- **A pure-move refactor that changes behaviour is the failure mode.** Move
  bodies verbatim first, tidy in a *separate* commit, so a bisect can tell the
  two apart.
- **Hidden `self.` dependencies.** Export handlers reach into the model, proxy,
  status bar, and settings. Each becomes an explicit parameter — that's the
  point, but it's where a missed attribute turns into an `AttributeError` at
  runtime rather than a test failure. Grep the moved bodies for every `self.`
  before declaring done.
- **Don't create a circular import** by having the new modules import
  `MainWindow` for typing. Use `TYPE_CHECKING` or a protocol.
- **Tests referencing `MainWindow._export_csv` etc. will break.** Update them to
  the new home rather than leaving compatibility shims — shims are how the old
  surface survives forever.
- **This will not hold without the rule.** If only the extractions land, expect
  3,581 again by autumn. The `CLAUDE.md` change is the load-bearing half.
- **Don't gate CI on line count.** A hard limit invites gaming (one 400-line file
  becomes two 200-line files with a worse boundary). Observation, not enforcement.

## Verification

- [x] `uv run pytest -q` in **one process**, locally, twice (before and after
      the export-format smoke test below) — 765 passed both times, exit code
      0. (This machine's CI counterpart already proved single-process,
      cross-platform green for the sibling plan today; not re-verified on
      GitHub Actions specifically for this change, but the same gate applies.)
- [x] `uv run ruff check .` / `ruff format --check .` clean, whole repo.
- [x] Line count: `main_window.py` **3,581 → 3,486 lines** (−95),
      **234 → 231 methods** (−3, via `ast` — the two extractions net out to
      few *fewer* top-level methods since each collapsed several private
      helpers into thin wrappers). Doesn't reach the aspirational ~3,000/~200
      — expected, this was deliberately modest (two extractions, not a
      carve-up) — recorded here, not enforced.
- [x] Manual: exercised every export path for real against a real
      `MainWindow` — `save_log`, `save_filtered_log`, CSV/JSON/HTML (the exact
      formatters `menus.py` wires up), PDF (real `%PDF` magic bytes), and a
      session bundle **round-tripped through a second MainWindow** (2 rows
      back). All wrote non-empty, readable files. This path had **no existing
      test coverage** for CSV/JSON/HTML/plain-log before or after this change
      — exactly the "writes but doesn't open" risk the plan called out, now
      covered by hand since automating it wasn't in scope.
- [x] adb-missing prompt still fires on Android intent, not at launch:
      covered directly by `tests/test_adb_setup_prompt.py`'s
      `test_prompt_never_fires_at_cold_start` and
      `test_prompt_fires_on_user_initiated_action_when_adb_resolves_nowhere`,
      both passing against the moved `adb_setup_flow.py` code.
- [x] `git diff` review: `main_window.py` is 58 insertions / 157 deletions —
      every removed body reappeared verbatim (parameterized) in
      `export_actions.py`/`adb_setup_flow.py`; the insertions are the thin
      wrapper calls. No formatter, dialog text, or control-flow logic changed.

## Open questions

- **Two extractions or three?** The theme/appearance handlers are a plausible
  third cluster. Leaning two — prove the rule works before spending more.
- **Is ~30 lines the right threshold in the rule?** Arbitrary but concrete;
  a fuzzy rule ("keep it thin") is one nobody can apply. Adjustable later.
- Should `add-zlog-feature` *check* the rule (fail loudly) or just state it?
  Leaning state — a skill that nags gets bypassed.
