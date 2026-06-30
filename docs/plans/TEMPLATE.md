# Plan: <Title>

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** <name>
- **Created:** <YYYY-MM-DD>
- **Related:** <other plans / issues, optional>

## Goal

One sentence: what a user can do after this ships that they can't now.

## Scope

- **In:** what this plan covers.
- **Out (non-goals):** what it deliberately does not cover.

## Design

Files to change and the layer each belongs to; functions/classes added or modified.

| File | Layer | Change |
|---|---|---|
| `src/zlog/...` | core / adb / ui | ... |

## Architecture touch points

- **Threading:** any background work and the signal it emits to reach the UI.
- **Model/proxy:** new column (`COLUMNS` + `data` + `headerData`) or new filter
  predicate (`filterAcceptsRow` + a setter calling `invalidateFilter`).
- **Dependency direction** respected (`ui → adb → core`)? Note anything subtle.

## Risks & regressions to check

- Start/stop streaming, autoscroll-at-bottom, clear, filtering while data flows.
- <feature-specific risks>

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Smoke / screenshot via `run-zlog` if the UI changed
- [ ] <feature-specific checks>

## Open questions

- <questions that block or shape the design>
