# Plans

zLog uses **plan-first** development: before writing code for any feature, fix, or
notable change, write a plan here and get it approved. Plans are living documents —
update the status as work proceeds, and mark it Done when shipped.

## Why

A short plan front-loads the thinking that keeps zLog's invariants intact (Qt-free
`core`, one-way `ui → adb → core` deps, workers reaching the UI only via signals,
a virtualized model). It also gives a place to agree on scope before code exists,
which is cheaper than reworking a built feature.

## How to use

- **One plan per purpose.** Split a large effort into several focused files
  (e.g. `device-picker.md`, `package-filter.md`, `save-load.md`) rather than one
  giant plan. A plan should be readable in a couple of minutes.
- **Start from the template.** Copy `TEMPLATE.md` to `docs/plans/<short-slug>.md`
  and fill it in.
- **Get it approved before implementing.** The `add-zlog-feature` and
  `review-zlog-ui` skills require an approved plan before code changes.
- **Keep the status line current:** `Draft → Approved → In progress → Done`
  (or `Abandoned`, with a one-line reason).
- **Keep this index updated** — add a row when you create a plan.

## Index

| Plan | Status | Summary |
|---|---|---|
| [device-picker.md](device-picker.md) | Done | Choose which connected device/emulator to stream from |
