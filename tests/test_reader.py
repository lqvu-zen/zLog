"""Tests for the adb logcat command builder (pure part of AdbReader)."""

from zlog.adb.reader import build_logcat_command


def test_default():
    assert build_logcat_command("adb", None) == ["adb", "logcat", "-v", "threadtime"]


def test_serial():
    assert build_logcat_command("adb", "ABC123") == [
        "adb",
        "-s",
        "ABC123",
        "logcat",
        "-v",
        "threadtime",
    ]


def test_buffers_and_bad_names_dropped():
    cmd = build_logcat_command("adb", None, ["main", "radio", "bogus"])
    assert cmd == ["adb", "logcat", "-v", "threadtime", "-b", "main", "-b", "radio"]


def test_tail():
    assert build_logcat_command("adb", None, tail=500) == [
        "adb",
        "logcat",
        "-v",
        "threadtime",
        "-T",
        "500",
    ]


def test_tail_zero_omitted():
    assert build_logcat_command("adb", None, tail=0) == ["adb", "logcat", "-v", "threadtime"]


def test_buffers_and_tail():
    assert build_logcat_command("adb", "S", ["main"], tail=100) == [
        "adb",
        "-s",
        "S",
        "logcat",
        "-v",
        "threadtime",
        "-b",
        "main",
        "-T",
        "100",
    ]


def test_since_time_maps_to_dash_T():
    cmd = build_logcat_command("adb", None, since_time="06-30 12:34:56.789")
    assert "-T" in cmd and cmd[cmd.index("-T") + 1] == "06-30 12:34:56.789"


def test_since_time_wins_over_tail():
    cmd = build_logcat_command("adb", None, tail=500, since_time="06-30 12:00:00.000")
    # only the timestamp form is present, not the count
    assert cmd.count("-T") == 1
    assert cmd[cmd.index("-T") + 1] == "06-30 12:00:00.000"


def test_should_flush_by_size_and_time():
    from zlog.adb.reader import _BATCH_SIZE, _FLUSH_INTERVAL, should_flush

    assert should_flush(0, 999) is False  # nothing buffered -> never
    assert should_flush(1, 0.0) is False  # small batch, no time elapsed -> hold
    assert should_flush(_BATCH_SIZE, 0.0) is True  # size cap
    assert should_flush(1, _FLUSH_INTERVAL) is True  # time cap keeps live latency low
    assert _BATCH_SIZE >= 1000  # coalesced so the initial dump doesn't flood the UI
