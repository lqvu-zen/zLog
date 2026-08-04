# Plan: Multi-line log entries

- **Status:** Draft — deferred; recorded so the decision isn't re-litigated
  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-03
- **Related:** [custom-log-format-preset.md](custom-log-format-preset.md), [custom-log-format-editor.md](custom-log-format-editor.md), [stack-trace-folding.md](stack-trace-folding.md), [wrap-messages.md](wrap-messages.md)

## Goal

An entry whose text spans several physical lines — a stack trace, a
pretty-printed JSON payload, a SQL statement — is treated as **one** log entry
with its continuation lines attached, rather than N entries where N−1 have no
timestamp, level, or tag.

## Status: deferred, deliberately

This is written now because it's the thing most likely to bite whoever implements
[custom-log-format-preset.md](custom-log-format-preset.md), and because "should we
just handle multi-line too?" will otherwise get asked mid-implementation and
answered under time pressure. **Don't start this without a specific, motivating
log.** It's the largest change of the three format plans by a wide margin.

## Why it's expensive

zLog is line-oriented end to end, and that's not incidental — it's what makes it
fast:

- **Readers** parse and emit per line: `adb/reader.py` (`for raw in stdout`),
  `ui/file_follower.py` (`split_complete_lines`), `cli.py`, `core/session.py`.
- **`LogEntry` is frozen with `slots=True`** — one line in, one immutable record
  out.
- **`LogTableModel`** is a flat virtualized list; row index maps 1:1 to entry.
- **`LogItemDelegate`** paints exactly one dense line per row.
- **The proxy** filters per row.

Making an entry own continuation lines touches every one of those. The
consequences that aren't obvious up front:

- **Batching becomes stateful.** A reader emitting in batches of ~50 can't know
  whether the last line of a batch is complete — the continuation may be in the
  next chunk, or may never arrive on a live stream that has gone quiet. You need a
  pending-entry buffer and a flush-on-idle rule, which is exactly the kind of
  timing logic that produced the follow-scroll flake.
- **Filtering gets ambiguous.** If a filter matches only a continuation line, is
  the entry shown? Both answers surprise someone.
- **Row counts stop meaning lines**, which affects the gutter line numbers,
  Ctrl+G "go to line", the scrollbar heat marks, and "Showing X of Y".
- **Export and copy** must decide whether to emit the joined entry or the original
  lines.

## What already exists, and may be enough

**[stack-trace-folding.md](stack-trace-folding.md) (Done)** solves the most common
case *presentationally*: `core/trace.py`'s `is_stack_frame` recognizes `at …` and
`… N more` lines, and folding hides them under the nearest preceding non-frame
line. Entries stay one-per-line — the model is untouched — but the user sees a
collapsed trace.

**[wrap-messages.md](wrap-messages.md) (Done)** already lets one entry render
across several visual rows.

So before building this, answer honestly: **is the real requirement "group these
lines" or "stop the trace flooding my view"?** If it's the latter, generalizing
`core/trace.py` to take a user-supplied continuation pattern is perhaps 20 lines
and no architectural change — and it composes with the format plans, since a
custom format could carry its own continuation regex.

That is the recommended first move, and it is **not** this plan.

## Scope (if it is ever built)

- **In:** a continuation rule per format (a regex, or "any line the format's main
  pattern doesn't match"); a grouping step between read and model; a decision on
  filter semantics; updates to line-number/goto/export semantics.
- **Out (non-goals):** reordering out-of-sequence lines, interleaved-thread
  reassembly (two threads writing traces at once — genuinely hard, and logcat
  itself doesn't solve it), and parsing structured payloads *within* a message.

## Design sketch

Two viable shapes, and the choice is the whole plan:

**A. Group at parse time — one `LogEntry` owns its continuations.**
`LogEntry` gains `continuation: tuple[str, ...]`. Readers buffer a pending entry
and flush it when a new entry-start line arrives *or* an idle timeout fires.
Cleanest data model; costs a stateful reader and a flush rule per source, and
`slots=True`/frozen means rebuilding rather than appending.

**B. Keep one row per line, mark continuations.**
`LogEntry` gains `is_continuation: bool`; the model stays flat; the proxy keeps a
continuation visible when its parent is; the delegate indents it. Much smaller
blast radius, no reader state, and it's the same shape as the folding feature
that already works. Costs: "one entry" remains a fiction for export and copy.

**B is recommended** on the evidence of stack-trace folding, which chose the
equivalent trade and has been fine.

## Architecture touch points

- **Threading:** shape A adds state and a timer to every reader — the highest-risk
  part, and the reason to prefer B. Any flush-on-idle must not touch widgets;
  signal only.
- **Model/proxy:** A changes what a row *is*; B leaves rows alone and changes only
  the filter's parent-child rule. Either way the model stays virtualized — never
  build a widget per row, never reset to append.
- **Dependency direction:** grouping logic is pure and belongs in `core/`,
  alongside `trace.py` and `tailer.py`.

## Risks & regressions to check

- **The live-stream tail is the hard case.** The last entry of a quiet stream has
  no successor to trigger its flush. Get this wrong and the newest line is
  invisible until the next one arrives — which on a low-traffic log could be
  minutes, and looks exactly like "zLog stopped working".
- **Don't regress the flat-file path** while chasing the stream case.
- **Filter semantics must be decided before coding**, not discovered.
- **Line numbers, Ctrl+G, heat marks, "Showing X of Y"** all silently change
  meaning under shape A — each needs a deliberate answer.
- **Interaction with the ring buffer** (`max_rows`): a group must not be half
  evicted, leaving orphan continuations.
- **Interaction with `fold_traces`**: two mechanisms hiding the same lines will
  fight. Decide which owns the behaviour; don't ship both.

## Verification

- [ ] A real multi-line log renders correctly from a **file**.
- [ ] The same content arriving on a **live stream** renders identically,
      including the final entry when the stream then goes quiet for 60s.
- [ ] The batch boundary case: a continuation split across two reader batches.
- [ ] Filtering behaves as the decision above specifies — with a test that pins it.
- [ ] Export, copy, line numbers, and Ctrl+G all still agree with each other.
- [ ] Existing stack-trace folding still works, or is deliberately retired.
- [ ] `uv run pytest -q` in one process (CI's command); local runs here are
      chunked and are not the full-suite gate.

## Open questions

- **Is generalizing `core/trace.py`'s continuation detection enough?** Answer this
  before anything else — it may close the whole plan for a fraction of the cost.
- **Shape A or B?** B recommended above.
- **Who supplies the continuation rule** — the format ([custom-log-format-editor.md](custom-log-format-editor.md))
  or a global setting? If the format plans land first, the format is the natural
  owner.
