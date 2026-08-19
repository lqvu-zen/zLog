"""Save/export flows: CSV/JSON/HTML/PDF, plain `.log` saves, session bundles,
and the redaction hookup shared by all of them.

One shared shape: gather the rows to write (the caller's job — `MainWindow`
already has `_filtered_entries`/`model.all_entries`), pick a path, write.
Every function here is free of `MainWindow` — it takes a parent widget for
dialogs, the data to write, and plain callables for the two things that must
reach back into the window (`report` for a status-bar message, and
`remember_recent` to add a path to the Open Recent list) — so this module can
never import `main_window` and stays independently testable.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from zlog.core.bundle import make_bundle
from zlog.core.export import to_print_html
from zlog.core.models import LogEntry
from zlog.core.redact import redact_entries
from zlog.core.session import entries_to_text
from zlog.core.symbolicate import Symbolicator
from zlog.ui.pdf_export import write_pdf

# Rendering more than this synchronously on the UI thread freezes zLog for too
# long to produce an unusably large file.
PDF_ROW_CAP = 50_000

Report = Callable[[str], None]


def maybe_redact(entries: list[LogEntry], redact: bool) -> list[LogEntry]:
    """Mask secrets when the caller's Redact-on-Export toggle is on; else pass
    through. Non-destructive — redaction runs on a copy, never the master list."""
    return redact_entries(entries) if redact else entries


def symbolicate_entries(
    entries: list[LogEntry], symbolicator: Symbolicator | None
) -> list[LogEntry]:
    """Deobfuscated/symbolicated copies of `entries` — same non-destructive
    shape as `redact_entries` (a copy via `dataclasses.replace`, master list
    untouched), skipping the copy for a message the symbolicator didn't
    change. Applied unconditionally whenever a `Symbolicator` is given:
    unlike redaction, this isn't hiding anything, so there's no separate
    opt-in toggle — export/copy just match what the live view already shows
    (see docs/plans/crash-symbolication.md)."""
    if symbolicator is None:
        return entries
    out = []
    for e in entries:
        new_message = symbolicator.apply(e.message)
        out.append(e if new_message == e.message else dataclasses.replace(e, message=new_message))
    return out


def write_log(
    parent: QWidget,
    entries: list[LogEntry],
    default_name: str,
    redact: bool,
    report: Report,
    remember_recent: Callable[[str], None] | None = None,
    symbolicator: Symbolicator | None = None,
) -> None:
    path, _ = QFileDialog.getSaveFileName(
        parent, "Save Log", default_name, "Log files (*.log);;All files (*)"
    )
    if not path:
        return
    entries = symbolicate_entries(entries, symbolicator)
    entries = maybe_redact(entries, redact)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(entries_to_text(entries))
    except OSError as exc:
        report(f"Could not save: {exc}")
        return
    redacted = " (redacted)" if redact else ""
    report(f"Saved {len(entries)} lines to {Path(path).name}{redacted}.")
    if remember_recent is not None:
        remember_recent(path)


def export_formatted(
    parent: QWidget,
    name: str,
    formatter: Callable[[list[LogEntry]], str],
    ext: str,
    entries: list[LogEntry],
    redact: bool,
    report: Report,
    symbolicator: Symbolicator | None = None,
) -> None:
    """Save `entries` via `formatter` (CSV/JSON/HTML/Markdown/message-only)."""
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    path, _ = QFileDialog.getSaveFileName(
        parent, f"Export {name}", f"zlog-{stamp}.{ext}", f"{name} (*.{ext});;All files (*)"
    )
    if not path:
        return
    entries = symbolicate_entries(entries, symbolicator)
    entries = maybe_redact(entries, redact)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(formatter(entries))
    except OSError as exc:
        report(f"Could not export: {exc}")
        return
    redacted = " (redacted)" if redact else ""
    report(f"Exported {len(entries)} lines to {Path(path).name}{redacted}.")


def export_pdf(
    parent: QWidget,
    entries: list[LogEntry],
    redact: bool,
    query_text: str,
    report: Report,
    symbolicator: Symbolicator | None = None,
) -> None:
    """Export `entries` to PDF, capped at PDF_ROW_CAP (see module docstring)."""
    entries = symbolicate_entries(entries, symbolicator)
    entries = maybe_redact(entries, redact)
    if len(entries) > PDF_ROW_CAP:
        reply = QMessageBox.question(
            parent,
            "Large export",
            f"The filtered view has {len(entries):,} lines. PDF export is capped at "
            f"{PDF_ROW_CAP:,} to avoid a huge, slow file — narrow the filter first for "
            "everything, or export just the first "
            f"{PDF_ROW_CAP:,} lines now?",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if reply != QMessageBox.Yes:
            return
        entries = entries[:PDF_ROW_CAP]
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    path, _ = QFileDialog.getSaveFileName(
        parent, "Export PDF", f"zlog-{stamp}.pdf", "PDF files (*.pdf);;All files (*)"
    )
    if not path:
        return
    doc_html = to_print_html(entries, title="zLog export", query=query_text)
    try:
        pages = write_pdf(doc_html, path)
    except OSError as exc:
        report(f"Could not export PDF: {exc}")
        return
    redacted = " (redacted)" if redact else ""
    report(f"Exported {len(entries)} lines ({pages} page(s)) to {Path(path).name}{redacted}.")


def write_session(
    path: str,
    all_entries: list[LogEntry],
    query_text: str,
    tag_colors: dict[str, str],
    bookmarks: dict[int, str],
    report: Report,
) -> None:
    text = make_bundle(entries_to_text(all_entries), query_text, tag_colors, bookmarks)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as exc:
        report(f"Could not save session: {exc}")
        return
    report(f"Saved session to {Path(path).name}.")


def save_session(
    parent: QWidget,
    all_entries: list[LogEntry],
    query_text: str,
    tag_colors: dict[str, str],
    bookmarks: dict[int, str],
    report: Report,
) -> None:
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    path, _ = QFileDialog.getSaveFileName(
        parent,
        "Save Session",
        f"zlog-{stamp}.zsession",
        "Session files (*.zsession);;All files (*)",
    )
    if path:
        write_session(path, all_entries, query_text, tag_colors, bookmarks, report)
