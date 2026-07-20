"""Tests for the large-file loader: the pure batch iterator and the QThread."""

from __future__ import annotations

from zlog.core.session import iter_entry_batches


def test_iter_entry_batches_sizes_and_remainder():
    lines = [f"line {i}" for i in range(0, 125)]
    batches = list(iter_entry_batches(lines, size=50))
    assert [len(b) for b in batches] == [50, 50, 25]  # remainder in the last batch
    # every line round-trips through parse_line (raw text preserved in message)
    flat = [e for b in batches for e in b]
    assert len(flat) == 125
    assert flat[0].message == "line 0" and flat[-1].message == "line 124"


def test_iter_entry_batches_empty_input():
    assert list(iter_entry_batches([], size=50)) == []


def test_iter_entry_batches_strips_newlines():
    (batch,) = list(iter_entry_batches(["hello\n"], size=50))
    assert batch[0].message == "hello"


def test_file_loader_emits_batches_and_done(qapp, tmp_path):
    from PySide6.QtCore import QEventLoop, QTimer

    from zlog.ui.file_loader import FileLoader

    path = tmp_path / "big.log"
    path.write_text("\n".join(f"07-15 20:09:03.024 100 200 I T: m{i}" for i in range(120)) + "\n")

    collected = []
    done = {}
    loader = FileLoader(str(path))
    loader.batch_ready.connect(lambda b: collected.extend(b))
    loader.done.connect(lambda n: done.setdefault("n", n))

    loop = QEventLoop()
    loader.done.connect(loop.quit)
    QTimer.singleShot(5000, loop.quit)  # safety net
    loader.start()
    loop.exec()
    loader.wait(2000)

    assert done.get("n") == 120
    assert len(collected) == 120
    assert collected[0].message == "m0" and collected[-1].message == "m119"
