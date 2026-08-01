# Plan: Run one CI job in shuffled test order

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-01
- **Related:** [fix-follow-scroll-flake.md](fix-follow-scroll-flake.md), [split-settings-tests.md](split-settings-tests.md), [ci-windows-job.md](ci-windows-job.md)

## Goal

Order-dependent tests are surfaced **deliberately by CI**, not accidentally by
whoever happens to run an unlucky subset.

## Why

We've already paid for this once. `test_follow_stays_manual_and_never_yanks`
failed depending on which subset of the suite ran before it — the worst kind of
red: real-looking, unrelated to the change in front of you, and it trains people
to re-run rather than investigate.

That one turned out to be a genuine product timing gap and was fixed at the root
in `519f9c5`. But the *class* of problem is still undetected: with ~1,000 tests
sharing a session-scoped `QApplication`, `QSettings`, and module-level state,
order coupling is easy to introduce and invisible until it isn't.

`fix-follow-scroll-flake.md` explicitly named this as the argument for a shuffled
job and put it out of scope. This plan is that follow-up.

**Sequencing:** do this **after** [ci-windows-job.md](ci-windows-job.md).
Platform coverage is the bigger gap, and adding two CI dimensions at once makes
a first red run ambiguous.

## Scope

- **In:** `pytest-randomly` as a dev dependency; one additional CI job running the
  suite in a shuffled order with a printed seed; documenting how to reproduce a
  shuffled failure locally.
- **Out (non-goals):** making the *default* job shuffled (a fixed order keeps the
  primary signal stable and comparable run-to-run), retry/rerun plugins — they
  hide exactly what this is meant to expose — parallelism (`pytest-xdist`), and
  fixing whatever this finds (separate plans, once we know).

## Design

One dependency, one job. Deliberately additive so the existing signal is untouched.

| File | Change |
|---|---|
| `pyproject.toml` | `pytest-randomly` in the `dev` extra. It seeds and shuffles, and — importantly — **prints the seed** on every run so a failure is reproducible. |
| `pyproject.toml` (`[tool.pytest.ini_options]`) | `-p no:randomly` in `addopts`, so the **default** local and CI runs stay in fixed order. Shuffling is opt-in via the job below. Without this, adding the plugin silently changes every existing run. |
| `.github/workflows/ci.yml` | A `shuffled` job (Linux, the fast platform): `uv run pytest -q -p randomly`. Runs on push/PR alongside the others. |
| `CLAUDE.md` / `docs/CONTRIBUTING.md` | How to reproduce: `uv run pytest -p randomly -p no:cacheprovider --randomly-seed=<seed>` using the seed from the failing log. A shuffled failure is useless without the seed, so make it impossible to miss. |

## Architecture touch points

- **Threading / model / dependency direction:** none. Tooling and config only.

## Risks & regressions to check

- **Expect this to go red on the first run.** That's success, not failure — it
  means the job found something a fixed order was hiding. But budget for it, and
  don't merge the job green-only by weakening it.
- **A shuffled failure with no seed is unfixable.** Verify the seed appears in the
  CI log output before relying on the job.
- **Don't let it become "allowed to fail".** A permanently-yellow job teaches
  people to ignore CI, which is worse than not having the job — the exact
  pathology the original flake was creating.
- **Adding the plugin must not change the default run.** Confirm `-p no:randomly`
  actually takes effect (compare collected order before/after).
- **Interaction with [split-settings-tests.md](split-settings-tests.md):** that
  split may itself surface latent order coupling. If both are in flight, land
  this job first so the split's failures are attributed correctly.
- **`QApplication` is session-scoped** — some shuffles may construct windows in an
  order that leaks. If that happens, the finding is about fixture scope, not about
  shuffling.

## Verification

- [ ] The shuffled job runs and prints its seed.
- [ ] Re-running with `--randomly-seed=<seed>` reproduces the same order (proves
      the reproduction path works *before* it's needed in anger).
- [ ] The default `uv run pytest -q` order is unchanged from today — diff the
      collected node-id list before and after adding the plugin.
- [ ] Deliberately introduce an order-dependent test (one that passes only if
      another ran first) → the shuffled job catches it within a few runs, the
      fixed job doesn't. This is the proof the job earns its minutes.
- [ ] Whatever real failures it finds are recorded as findings, each getting its
      own plan rather than a quick patch.

## Open questions

- **Should it run on every PR, or nightly?** Every PR gives immediate feedback but
  a nondeterministic job on the merge path is contentious. Leaning every PR while
  the suite is small (~1,000 tests, fast on Linux); move to nightly if it becomes
  noisy.
- **`pytest-randomly` also reseeds `random`/`faker` per test.** Harmless here (we
  don't use randomized data), but worth confirming nothing depends on a fixed
  global seed.
- Should the shuffled job also run on Windows? Not initially — one new dimension
  at a time.
