# Plan: Column-width polish

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-06-30
- **Related:** first fix surfaced by `review-zlog-ui` screenshots (Time wraps to 2 lines)

## Goal

Stop the **Time** column wrapping to two lines and give the narrow columns sensible
default widths, so the table reads cleanly at the default window size.

## Scope

- **In:** set default widths for Time/PID/TID/Level/Tag so their content fits on one
  line; keep **Message** stretching to fill the rest; keep columns user-resizable.
- **Out:** per-column show/hide; saving column widths across launches; font changes.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | After building the table, set the header resize modes: `Message` stays `Stretch`; the others `Interactive` with explicit initial widths via `setColumnWidth` — roughly Time 145, PID 60, TID 60, Level 55, Tag 170 (tuned against the `populated` screenshot). This keeps `Time` (`06-30 12:34:56.789`) on one line while leaving columns draggable. |
| `.claude/skills/run-zlog/scripts/driver.py` | (skill) | reuse `populated`/`dark` to verify; no new scenario. |

## Architecture touch points

- **Threading/model:** none — pure view configuration. Using fixed initial widths
  (not `ResizeToContents`, which would measure every row and hurt large logs) keeps
  the virtualized model fast.
- **Dependency direction:** UI-only.
- **Versioning:** no bump (release-only).

## Risks & regressions to check

- Time shows on one line at the default 1100px width.
- Message still stretches and no column is clipped awkwardly.
- Columns remain draggable; narrow window degrades gracefully (horizontal scroll).

## Verification

- [x] `uv run pytest` (unchanged; still green)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` `populated` screenshot shows a single-line Time column
- [ ] Manual: resize the window narrow/wide → layout stays sane

## Open questions

- Exact default widths (values above are a starting point tuned from the screenshot).
- Right-align PID/TID for scanability (nice-to-have) — include now or later?
