# Plan: Fix the order-dependent follow-scroll flake

- **Status:** Abandoned — fixed in production code instead (see note below)
  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-24
- **Related:** [smart-follow.md](smart-follow.md), [wrap-refit-on-resize.md](wrap-refit-on-resize.md), [file-follow.md](file-follow.md)

## Goal

Make `test_follow_stays_manual_and_never_yanks` deterministic, so CI stays
trustworthy instead of failing at random and training everyone to ignore red.

## Why

The test asserts `sb.value() == sb.maximum()` — pixel-exact — after a fixed
`QTest.qWait(150)`. Two things make that unreliable, and **both** are timing,
not a product bug:

1. The follow scroll is **coalesced onto a timer**, so 150 ms is a guess. If the
   machine is loaded (or a previous test warmed things differently) the scroll
   may not have run yet.
2. `_do_follow_scroll` deliberately scrolls **twice** — scroll, re-fit the newly
   revealed wrapped rows, scroll again (see `wrap-refit-on-resize.md`). Between
   those, `maximum()` grows. Landing a few pixels short is a legitimate
   intermediate state, not a failure.

Observed: `value=982, maximum=985` — 3 px short. It reproduces on an
**unmodified baseline**, so it predates the recent work; it passes or fails
depending on which subset of the suite runs before it. That's the worst kind of
red: real-looking, unrelated to the change in front of you.

## Scope

- **In:** replace the fixed wait + exact-equality assertion in the follow tests
  with a settle-then-assert helper and a sub-row tolerance; share one wait helper
  across the suite (`test_file_follower.py` already grew its own `_wait_for`).
- **Out (non-goals):** changing `_do_follow_scroll`'s two-pass behaviour (it's
  correct and was added to fix a real bug), adding `pytest-randomly`, retry
  plugins, or touching the other 9 `qWait` call sites unless they prove flaky
  too — this plan fixes the one that demonstrably fails.

## Design

The behaviour under test is **"Follow keeps you tailing"** — not "the scrollbar
integer equals another integer". Assert that, and remove the guessed sleep.

| File | Layer | Change |
|---|---|---|
| `tests/conftest.py` | — | `wait_until(qapp, predicate, timeout_ms=2000)` — spin the event loop until the predicate holds or the timeout expires, returning the final value. Replaces "sleep a guessed amount, then hope". Also `at_bottom(scrollbar, slack)` expressing the real condition: within `slack` px of the maximum. |
| `tests/test_main_window_settings.py` | — | The three `sb.value() == sb.maximum()` assertions become `wait_until(qapp, lambda: at_bottom(sb))`. Slack defaults to one row height (from the delegate/`fontMetrics`), so a mid-refit residue passes while a genuine "didn't follow" (hundreds of px, or 0) still fails. The `sb.value() == 0` assertion **stays exact** — "didn't move" is exact by nature and is the anti-yank guarantee worth keeping strict. |
| `tests/test_file_follower.py` | — | Drop its private `_wait_for`/`_settle` in favour of the shared helper, so there's one wait idiom. |

## Architecture touch points

- **Threading:** none — test-only change. No production code is touched, which
  is the point: the product behaviour is correct.
- **Model/proxy:** none.
- **Dependency direction:** unaffected.

## Risks & regressions to check

- **Don't weaken the test into uselessness.** Slack must be ~one row, not
  "anything close". A regression where Follow stops working leaves the view
  hundreds of pixels up (or at 0) and must still fail. Verify by temporarily
  breaking `_do_follow_scroll` and confirming the test goes red.
- **The anti-yank assertion must stay exact** (`value == 0`): loosening that one
  would hide the actual bug this test was written for.
- **`wait_until` must not mask a hang** — bounded timeout, and the assertion
  after it still has to hold, so a never-satisfied predicate fails rather than
  passing silently.
- Confirm the fix under **adverse ordering**, not just in isolation: run the file
  both alone and in the subsets where it currently fails (e.g. node ids 41–79).
- The other 9 `qWait` sites in this file may share the weakness; note any that
  fail during verification rather than pre-emptively rewriting them.

## Verification

- [ ] The previously-failing subset passes: `pytest $(sed -n '41,79p' <node-ids>)`
      — the exact grouping that reproduced it.
- [ ] `uv run pytest` in **one process** (CI's command), not chunked — this is the
      run that actually proves ordering independence.
- [ ] Repeat the full run 3× to catch residual nondeterminism.
- [ ] Deliberately break `_do_follow_scroll` → the test must fail. (Proves the
      loosened assertion still has teeth.)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`

## Open questions

- **Slack size:** one row height (computed) vs. a fixed small constant (e.g. 8 px).
  Leaning computed — it stays correct if the font or density changes.
- Should `wait_until` live in `conftest.py` as a fixture or a plain importable
  helper? Leaning a plain function imported from a `tests/support.py`, since
  `test_file_follower.py` wants it at module level too.
- Worth adding a CI job that runs the suite with `-p no:randomly` **and** a
  shuffled order, to surface ordering bugs deliberately rather than by luck?
  Out of scope here, but this flake is the argument for it.

## 2026-07-30 update: abandoned — fixed at the root instead

Found independently while running the 1.0.0 release gate (before noticing this
plan): the failure reproduced 5/5 in isolation, not just under adverse ordering,
and traced to a genuine product timing gap — `_do_follow_scroll`'s scrollbar
`maximum()` was still growing on the *next* event-loop turn after its scroll
passes, so even the wrap-mode re-pin could land short. Fixed in
`519f9c5` ("Fix follow-scroll one-row lag and stale device-picker test
assumptions") by adding a third, deferred re-pin (`QTimer.singleShot(0, ...)`)
that re-checks the Follow/selection guards and re-pins once the range has
settled — production code, not the test. Held across 5/5 isolated reruns and
two full-suite passes (0 failures) afterward.

This plan's diagnosis of *why* a fixed-wait pixel-exact assertion is fragile
remains correct in general, and its settle-then-assert helper is still a
reasonable hardening if this or a similar test misbehaves again — but the
specific failure it was written against is gone at the source, so building the
test-only workaround on top would be solving an already-solved problem. Not
verified under the adverse/shuffled subset ordering this plan calls for
(out of scope for this update); worth a look if the test ever flakes again.
