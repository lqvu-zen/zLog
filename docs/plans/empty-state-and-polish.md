# Plan: Empty-state hint + table polish

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-06-30
- **Related:** follow-up to a `review-zlog-ui` pass (see the review report)

## Goal

Replace the blank empty table with a helpful placeholder, and apply three small
readability tidies from the UI review.

## Scope

- **In:**
  - **M1** — a centered placeholder in the table when nothing is shown, with
    contextual text (nothing captured yet vs. filtered to nothing).
  - **L1** — right-align the PID and TID columns.
  - **L2** — enable alternating row colors (uses the theme's `alt_base`).
  - **L3** — rename the package **Filter** button to **Apply**.
- **Out (non-goals):** L4 (banner vs level filter) — left as an open question below;
  persisting anything; other review items.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_model.py` | ui | `data()` returns `Qt.AlignRight | Qt.AlignVCenter` for `TextAlignmentRole` on the PID (1) and TID (2) columns. |
| `src/zlog/ui/table_view.py` (new) | ui | `LogTableView(QTableView)` that paints a centered `placeholder` string over the viewport when the shown row count is 0. `set_placeholder(text)` stores it and repaints. Small, self-contained. |
| `src/zlog/ui/main_window.py` | ui | Use `LogTableView`; call `setAlternatingRowColors(True)`. Add `_update_placeholder()` that sets the text from state (streaming? any rows in the model? a filter active?) and call it after start/stop, load, clear, and whenever a filter changes. Rename the button label "Filter" → "Apply" (keep the method name `apply_package_filter`). |
| `.claude/skills/run-zlog/scripts/driver.py` | (skill) | an `empty` scenario (idle, no rows) to screenshot the placeholder; reuse `populated` for alignment/banding. |

## Architecture touch points

- **Threading/model:** none new. The placeholder is a paint-time overlay driven by
  `proxy.rowCount()`; the model stays virtualized and the master list untouched.
- **Colors:** alternating-row color already lives in `ui/theme.py`; we only enable
  it. Placeholder text uses the current palette (no new hard-coded hex).
- **Dependency direction:** all changes in `ui`; `core` untouched, still Qt-free.
- **Versioning:** no bump (release-only).

## Risks & regressions to check

- Placeholder shows only when empty and disappears as soon as rows appear.
- Placeholder text is correct in both cases (no device / filtered-to-nothing).
- Right-aligned PID/TID don't misalign headers; Message still stretches.
- Alternating rows look right in **both** Light and Dark (check contrast with tints).
- Renamed button still applies the package filter (Enter in the field too).

## Verification

- [x] `uv run pytest` (still green; PID/TID alignment verified via screenshot — a model test would need Qt, which the suite avoids)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` `empty` screenshot shows the placeholder; `populated`/`dark` show
      right-aligned PID/TID and row banding
- [ ] Manual: filter to nothing → "no matches" text; clear → rows return

## Open questions

- L4: should unparsed banner lines be **hidden when min level > V** (proposed:
  leave as-is for now) — decide separately?
- Placeholder wording — the two strings above, or shorter?
