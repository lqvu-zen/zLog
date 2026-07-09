# Plan: Doc sync for the Android-Studio-style redesign

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-09
- **Related:** logcat-style-ui.md (the redesign these docs must now describe)

## Goal

Bring the user- and developer-facing docs in line with the redesigned UI (dense
line-per-entry delegate, single query bar, icon rail, ⋮ overflow) so the docs match
the app again.

## Scope

- **In:** rewrite `docs/GUIDE.md` for the new UX + regenerate its screenshots;
  update the data-flow / "where things live" / architecture notes in `README.md`,
  `CLAUDE.md`, and `docs/ARCHITECTURE.md` (delegate view, `core/query.py` parser,
  query bar, overflow; column-visibility retired).
- **Out:** no code changes; no new features.

## Design

| File | Change |
|---|---|
| `docs/GUIDE.md` | Rewrite: streaming via the rail, filtering via the **query bar** (`level: tag: package: -exclude /regex/`), overflow menu for themes/save/zoom/bookmarks/presets. New screenshots. |
| `docs/images/*` | Regenerate against the new UI (streaming, a query filter, light+dark). Remove stale grid-UI shots. |
| `README.md` | Fix the data-flow block (delegate list, query bar) and the stale "where to go next". |
| `CLAUDE.md` | Update the data-flow diagram, the "Where things live" table (`ui/log_delegate.py`, `core/query.py`), and the `ui/` description. |
| `docs/ARCHITECTURE.md` | Update the `ui/` section (delegate + query parser) and the end-to-end data flow. |

## Verification

- [ ] All doc image links resolve; screenshots show the new UI.
- [ ] No doc still describes the grid table / two-row toolbar / column visibility as current.
- [ ] `uv run pytest` / ruff unaffected (docs only).
