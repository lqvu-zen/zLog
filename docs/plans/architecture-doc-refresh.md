# Plan: Refresh ARCHITECTURE.md and ROADMAP.md

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-01
- **Related:** [windows-debug-output.md](windows-debug-output.md), [file-follow.md](file-follow.md), [main-window-split.md](main-window-split.md), [main-window-drift.md](main-window-drift.md)

## Goal

`docs/ARCHITECTURE.md` describes the app that exists, not the Android-only logcat
viewer it was six weeks ago.

## Why

Both docs contain **zero** mentions of `winlog`, `dbwin`, `file_follower`,
`capture_controller`, or `tabstate` — five modules that carry roughly half of
what zLog now does. `ARCHITECTURE.md` still opens with "three layers map to three
packages"; there are **four** (`core`, `adb`, `winlog`, `ui`).

`CLAUDE.md` *is* current — its "Where things live" table lists every new module —
so the load-bearing doc is fine and nothing is at risk of being coded wrong. The
problem is narrower and still real: `ARCHITECTURE.md` is the doc a human opens to
understand the design, and right now it **actively misleads**. It says Windows
capture doesn't exist. Someone reading it would conclude `AdbReader` is the only
reader and put new capture logic in the wrong place.

Docs debt compounds quietly: the further behind it gets, the less anyone trusts
it, and the point at which nobody reads it is the point at which writing it was
wasted.

## Scope

- **In:** update `ARCHITECTURE.md` to describe four packages, the reader family
  and its shared contract, `CaptureController`, and tab state/persistence; update
  `ROADMAP.md` to reflect what shipped and what's actually next.
- **Out (non-goals):** rewriting `CLAUDE.md` (already correct), `docs/GUIDE.md`
  (user-facing, tracked separately), generated API docs, and diagram tooling.

## Design

Two docs, prose only. The structure is right; the content is stale.

| File | Change |
|---|---|
| `docs/ARCHITECTURE.md` | **Four layers, not three.** Add `winlog/` alongside `adb/` as a peer *source* package (Windows-only, imported lazily, guarded by `is_supported()`). Generalize the reader section from "`AdbReader` does X" to **the reader contract** every source honours: run off-thread, parse to `LogEntry`, emit `batch_ready` in batches, never touch a widget — then list the implementations (`AdbReader`, `DebugOutputReader`, `EvtLogReader`, `LaunchReader`, `FileFollower`). That framing is the durable one: the next source slots in without another rewrite. |
| `docs/ARCHITECTURE.md` | Add `CaptureController` — attach/detach per session, owns `extra_readers` — as the seam between "a reader" and "the window". Add the `core/tabstate.py` + `core/tabtitle.py` pair and how open tabs survive a restart. Note `core/dbwin.py`/`core/winevent.py` as the **pure** halves of the Windows features, and say *why* they're split out (they're the part that can be tested anywhere — this is the reason the `core/` rule keeps earning its keep). |
| `docs/ROADMAP.md` | Move shipped items out of "planned". Reflect the current position: the Windows sources are done; [etw-tracing.md](etw-tracing.md) is the one open Draft; the tech-debt plans are the near-term non-feature work. |
| `README.md` | Its "Project layout" tree still shows only `core/{models,parser}`, `adb/`, `ui/{log_model,main_window}` — stale in the same way. Update the tree. |

## Architecture touch points

- **Threading / model / dependency direction:** none — but the doc must *state*
  these correctly, since they're the invariants it exists to teach. Re-read the
  rules in `CLAUDE.md` while writing so the two don't contradict each other.

## Risks & regressions to check

- **Don't duplicate `CLAUDE.md`.** Two sources of truth drift, and then both are
  suspect. `CLAUDE.md` = the load-bearing summary and file map; `ARCHITECTURE.md`
  = the *why*. Cross-link rather than restate the table.
- **Don't document aspirations as fact.** Describe what the code does today; if
  something is planned, it belongs in `ROADMAP.md`.
- **Verify against the code, not memory** — read each module before describing it.
  A confidently wrong architecture doc is worse than a stale one.
- **Keep it short.** The reason it went stale is that updating it felt like a
  chore; a tighter doc gets updated.

## Verification

- [ ] `grep -c` for `winlog`, `dbwin`, `file_follower`, `capture_controller`,
      `tabstate` in `docs/ARCHITECTURE.md` — all non-zero.
- [ ] Every module named in the doc exists at the path given (spot-check by
      opening each).
- [ ] No statement in `ARCHITECTURE.md` contradicts `CLAUDE.md`'s rules section.
- [ ] README's layout tree matches `ls src/zlog/**`.
- [ ] A cold read: does someone who's never seen the repo end up putting a new
      log source in the right package? That's the doc's actual job.

## Open questions

- **Should `winlog/` be described as a peer of `adb/` or as a sibling family with
  a shared base?** They share a contract but no base class today. Leaning
  "document the contract, note there's no ABC and that's deliberate" — inventing
  an abstract base just to make the doc tidier would be the tail wagging the dog.
- Worth a small ASCII data-flow diagram covering all five readers, like the one in
  the README? Probably yes — it's the fastest way to show they converge on one
  model.
