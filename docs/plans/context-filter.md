# Plan: Right-click quick-filter from a log line

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** [mute-tag.md](mute-tag.md), [logcat-style-ui.md](logcat-style-ui.md) (query bar)

## Goal

After this ships, right-clicking a log line offers **Filter to…** (Level ≥ X, Tag:
Y) and **Exclude…** (Tag: Y), which add the clicked line's element as a token to
the current query — so you can build a filter by clicking, not typing.

## Scope

- **In:** context-menu submenus that append/replace `level:`/`tag:` tokens in the
  query bar (single filtering path); exclude reuses the existing mute-tag.
- **Out:** PID/process filtering (the query has no `pid:` token; it would tangle
  with the live package-filter machinery — a separate effort), filtering by the raw
  message text, regex-escaping message fragments.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | `import shlex`. `_add_query_token(token)` re-emits the query with any same-key token replaced by `token`, quoting tokens that contain spaces (so a tag with spaces round-trips through `parse_query`). In `_show_table_menu`, capture the clicked `entry`; add a **Filter to…** submenu (Level ≥ `{level}`, Tag: `{tag}`) → `_add_query_token(...)`, and an **Exclude…** submenu (Tag → existing `_mute_tag`). |
| `tests/test_main_window_settings.py` | tests | `_add_query_token` adds a token, replaces a same-key one, and a spaced tag round-trips via `parse_query`. |

## Architecture touch points

- **Single filtering path:** everything flows through the query bar → `parse_query`
  → proxy, so no new gate; presets/history keep working.
- **Quoting:** rebuild via `shlex.quote` for spaced tokens so `parse_query` (which
  uses `shlex.split`) reads them back correctly.

## Risks & regressions to check

- **Don't mangle the existing query:** re-emit preserves other tokens; spaced values
  are quoted; an unparseable query falls back to a plain split.
- **Replace vs. add:** a second `level:` replaces the first (one level floor);
  `tag:` likewise (one tag gate).

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: right-click a line → Filter to Tag; the query gains `tag:…` and filters.
