"""Tests for the pure sparkline rendering. No Qt required."""

from zlog.core.models import LEVEL_RANK
from zlog.core.sparkline import error_rate_sparkline, sparkline

E = LEVEL_RANK["E"]
INFO = LEVEL_RANK["I"]


def test_sparkline_scaling():
    assert sparkline([]) == ""
    assert len(sparkline([0, 1, 2, 3, 4])) == 5
    assert sparkline([0, 0, 0]) == "▁▁▁"  # flat baseline when all zero
    assert sparkline([1, 2])[1] == "█"  # the max maps to the full block
    assert sparkline([1, 2])[0] != "█"


def test_error_rate_sparkline_towers_on_errors():
    ranks = [INFO] * 10 + [E] * 10  # errors concentrated in the second half
    s = error_rate_sparkline(ranks, E, buckets=2)
    assert len(s) == 2
    assert s[0] == "▁" and s[1] == "█"  # bucket 0: no errors, bucket 1: all
    assert error_rate_sparkline([], E) == ""
