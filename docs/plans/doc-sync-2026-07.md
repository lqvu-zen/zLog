# Plan: Doc sync — GUIDE + README (2026-07)

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-14

## Why

GUIDE.md and README.md predate a batch of shipped features and now misdirect the
reader (preferences moved out of the View menu into a Settings dialog; new columns,
filters, and modes are undocumented).

## Scope (text only; screenshots left as-is this pass)

**docs/GUIDE.md**
- "Window at a glance": add the **Settings** menu entry + **Saved Filters** sidebar; note device **tabs**.
- Query-bar table: add `pid:` and `proc:` rows; note right-click **Filter to… Level/Tag/PID/Package**.
- Move Highlight / Theme / Time display instructions to their homes in **Settings**.
- New sections: **Settings** (4 tabs), **Process/package names**, **Wrap long messages**, **Tabs & New Window**, **Command palette**.
- Filter presets: mention the sidebar (save/apply/rename/update/preview/delete).

**README.md**
- Add `pid:`/`proc:` to the query tokens + proxy data-flow line; refresh the Features paragraph.

## Verification

- [ ] Markdown links resolve; no stale "View → Theme/Search options/Time display".
- [ ] `uv run pytest` (unaffected) + ruff clean (docs don't affect code).
