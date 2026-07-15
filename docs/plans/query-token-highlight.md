# Plan: Highlight recognized tokens in the query bar

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-14
- **Related:** [logcat-style-ui.md](logcat-style-ui.md), quick-filter-pid-package.md

## Goal

Color the recognized filter tokens right in the query bar (`level:` `tag:`
`package:`/`pkg:`/`app:` `pid:` `proc:`/`process:` `-exclude` `/regex/`) so the
filter's structure is visible at a glance, like the mock the user shared.

## Design (Approach A — overlay on the existing QLineEdit)

- **`core/query.py`:** add pure `token_spans(text) -> [(start, end, kind)]` — a
  quote-aware positional scanner that returns each token's character span and its
  `kind` (`level|tag|package|proc|pid|exclude|regex|word`). Unit-tested.
- **`ui/query_line_edit.py` (new):** `QueryLineEdit(QLineEdit)` overrides
  `paintEvent`: after the base paint, draw a translucent rounded rectangle behind
  each recognized token (skip `word`). Token x-positions come from `QFontMetrics`
  over the text, offset by the line-edit's text origin and clipped to the content
  rect (so highlights never spill past the box). Keeps the clear button,
  completer, Enter-to-save, and error tint intact.
- **`ui/main_window.py`:** construct the query bar as `QueryLineEdit` instead of
  `QLineEdit` (one-line change; all `self.query.*` calls unchanged).

Colors (translucent so they read on both themes): level=amber, tag=teal,
package/proc/pid=green/blue, exclude=red, regex=purple.

## Limits / risks

- Positions are font-metric based; a very long query that scrolls sideways can
  drift — mitigated by clipping to the visible content rect. Common short queries
  are exact.
- Translucent fill is drawn over the text (readable); true behind-text rendering
  would require re-drawing the text ourselves (out of scope).

## Verification

- [ ] `uv run pytest` — `token_spans` cases (kinds, quotes, exclude, regex, unknown key)
      + a QueryLineEdit smoke test (no crash on paint).
- [ ] ruff clean; manual: tokens light up as you type; clear button/completer still work.
