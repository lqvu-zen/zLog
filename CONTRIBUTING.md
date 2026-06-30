# Contributing to zLog

Thanks for your interest in zLog — a Windows-first desktop viewer for Android
`adb logcat`, built with Python + PySide6 and managed with [uv](https://docs.astral.sh/uv/).

## Getting set up

```bash
uv sync --extra dev     # create the venv with app + dev tools
uv run zlog             # launch the app (needs adb + a device/emulator)
uv run pytest           # run the test suite
```

A live run needs Android platform-tools (`adb`) on your PATH and a connected
device or emulator. The tests need neither.

## Before you open a PR

Please make sure these all pass — CI runs the same checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Run `uv run ruff format .` to auto-fix formatting.

## Architecture rules (read these first)

zLog has three layers — `core/` (pure, Qt-free), `adb/` (the streaming thread),
`ui/` (Qt). A change that ignores them can freeze the UI or create import cycles.
The essentials:

- **`core/` never imports Qt.** Qt-free logic lives there so it stays testable.
- **Dependency direction is one-way: `ui` → `adb` → `core`.** Never import
  `zlog.ui.*` from a lower layer.
- **Worker threads never touch widgets directly** — communicate via Qt signals
  delivered to the main thread (see `AdbReader.batch_ready`).
- **Keep the table model virtualized** and **filter through the proxy**, not by
  mutating the master list.
- **Bump `__version__`** in `src/zlog/__init__.py` (and `version` in
  `pyproject.toml`) with each change.

The full reasoning is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); a quick
reference is in [`CLAUDE.md`](CLAUDE.md).

## Tests

Add a unit test whenever you add testable non-UI logic (a parser case, a filter
rule). Put it in `tests/`, matching the style of `tests/test_parser.py`. Pure-UI
changes usually have nothing to unit-test — verify those by running the app.

## Commits & PRs

- Keep changes focused; avoid bundling unrelated refactors.
- Write a clear commit message describing what changed and why.
- Make sure the checks above are green before requesting review.

## License

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
