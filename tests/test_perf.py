"""Perf smoke tests — guard the hot paths (append + filter) against O(n^2)
regressions like the Start-freeze bugs.

These assert *generous* wall-clock budgets: the point is to catch a quadratic
blow-up (seconds → minutes), not to micro-benchmark. They run under the offscreen
Qt platform (see conftest.py) and touch no widgets, so they stay CI-stable.
"""

from __future__ import annotations

import time

from zlog.core.models import LogEntry
from zlog.ui.log_model import LogFilterProxy, LogTableModel

_N = 60_000  # a busy on-device buffer dumped on Start
_BATCH = 2_000  # matches AdbReader._BATCH_SIZE


def _make_entries(n: int) -> list[LogEntry]:
    levels = ("V", "D", "I", "W", "E")
    return [
        LogEntry(
            f"07-15 20:09:{i % 60:02d}.{i % 1000:03d}",
            str(1000 + i % 50),
            str(2000 + i % 50),
            levels[i % len(levels)],
            f"Tag{i % 40}",
            f"message number {i} lorem ipsum dolor sit amet",
        )
        for i in range(n)
    ]


def test_append_in_batches_is_linear(qapp):
    """Appending 60k rows in reader-sized batches must stay well under budget.

    ResizeToContents-style O(n^2) sizing turned this into ~40s; virtualized
    appends keep it a fraction of a second.
    """
    model = LogTableModel()
    proxy = LogFilterProxy()
    proxy.setSourceModel(model)
    entries = _make_entries(_N)

    start = time.monotonic()
    for i in range(0, _N, _BATCH):
        model.append_entries(entries[i : i + _BATCH])
    elapsed = time.monotonic() - start

    assert model.rowCount() == _N
    assert elapsed < 10.0, f"append of {_N} took {elapsed:.2f}s (expected << 10s)"


def test_filter_over_large_model_is_fast(qapp):
    """Applying and clearing filters over a 60k model must be quick (the proxy
    re-runs filterAcceptsRow per row, not per row per row)."""
    model = LogTableModel()
    proxy = LogFilterProxy()
    proxy.setSourceModel(model)
    model.append_entries(_make_entries(_N))

    start = time.monotonic()
    proxy.set_min_level("W")  # gate ~40% of rows
    visible_filtered = proxy.rowCount()
    proxy.set_search("number 1", regex=False)
    proxy.set_min_level("V")
    proxy.set_search("", regex=False)
    elapsed = time.monotonic() - start

    assert 0 < visible_filtered < _N  # the filter actually gated something
    assert proxy.rowCount() == _N  # cleared back to everything
    assert elapsed < 10.0, f"filter cycle over {_N} took {elapsed:.2f}s (expected << 10s)"
