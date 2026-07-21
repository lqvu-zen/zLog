"""Tests for the timeline bucketizer (pure, no Qt)."""

from __future__ import annotations

from datetime import datetime

from zlog.core.histogram import bucketize


def _t(sec):
    return datetime(2026, 7, 15, 20, 9, sec % 60)


def test_empty_and_nonpositive():
    assert bucketize([], [], 10) == []
    assert bucketize([_t(0)], ["I"], 0) == []


def test_even_time_split_and_first_index():
    # 4 rows spanning 0..30s into 2 buckets -> [0,15) and [15,30]
    times = [_t(0), _t(10), _t(20), _t(30)]
    levels = ["I", "I", "I", "I"]
    b = bucketize(times, levels, 2)
    assert len(b) == 2
    assert b[0].count == 2 and b[1].count == 2
    assert b[0].first_index == 0 and b[1].first_index == 2


def test_error_count_only_warn_and_above():
    times = [_t(0), _t(1), _t(2)]
    levels = ["I", "W", "E"]
    (bucket,) = bucketize(times, levels, 1)
    assert bucket.count == 3 and bucket.error_count == 2  # W + E, not I


def test_unparseable_time_folds_into_previous():
    times = [_t(0), None, _t(30)]
    levels = ["I", "I", "E"]
    b = bucketize(times, levels, 2)
    # row 1 (None) folds into row 0's slot; row 2 lands in the last slot
    assert b[0].count == 2 and b[1].count == 1
    assert b[1].error_count == 1


def test_no_parseable_times_falls_back_to_even_index_split():
    times = [None, None, None, None]
    levels = ["I", "I", "E", "I"]
    b = bucketize(times, levels, 2)
    assert [x.count for x in b] == [2, 2]  # even split by index
    assert b[0].first_index == 0 and b[1].first_index == 2
