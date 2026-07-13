"""Tests for the pure scrollbar heat-mark bucketing. No Qt required."""

from zlog.core.heat import heat_marks
from zlog.core.models import LEVEL_RANK

E = LEVEL_RANK["E"]
INFO = LEVEL_RANK["I"]


def test_errors_at_ends_map_to_first_and_last_buckets():
    ranks = [E] + [INFO] * 8 + [E]  # 10 rows, errors at index 0 and 9
    marks = heat_marks(ranks, 10, E, buckets=10)
    assert 0.0 in marks and 0.9 in marks
    assert all(0.0 <= m < 1.0 for m in marks)


def test_no_errors_and_empty():
    assert heat_marks([INFO, INFO, INFO], 3, E) == []
    assert heat_marks([], 0, E) == []


def test_mark_count_is_bounded_by_buckets():
    ranks = [E] * 10000
    marks = heat_marks(ranks, 10000, E, buckets=50)
    assert len(marks) <= 50


def test_generator_input_supported():
    ranks = (E if i == 5 else INFO for i in range(10))
    assert heat_marks(ranks, 10, E, buckets=10) == [0.5]
