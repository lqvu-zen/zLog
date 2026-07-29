"""Render a :class:`QTextDocument` to a paginated PDF with a page-number footer.

`QTextDocument.print_()` alone paginates but draws no footer; Qt has no CSS
support for one (its HTML/CSS renderer is not a browser engine — no
`@page`/`counter()`). So pagination is done by hand: lay the document out once
at the page size, then for each page translate the painter so that page's
slice lands on the sheet, clip out the footer strip, draw, and stamp
"Page N of M" in the strip. This is the pattern Qt's own print examples use.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSizeF, Qt
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter, QTextDocument

_FOOTER_HEIGHT = 24  # device pixels at the writer's resolution


def write_pdf(html: str, path: str, *, landscape: bool = True) -> int:
    """Write `html` to `path` as a PDF. Returns the page count."""
    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageOrientation(QPageLayout.Landscape if landscape else QPageLayout.Portrait)

    doc = QTextDocument()
    doc.setHtml(html)

    page_rect = writer.pageLayout().paintRectPixels(writer.resolution())
    doc.setPageSize(QSizeF(page_rect.width(), page_rect.height() - _FOOTER_HEIGHT))
    page_count = max(1, doc.pageCount())

    painter = QPainter()
    if not painter.begin(writer):
        raise OSError(f"Could not open {path!r} for writing")
    try:
        content_height = page_rect.height() - _FOOTER_HEIGHT
        for page in range(page_count):
            if page > 0:
                writer.newPage()
            painter.save()
            painter.setClipRect(QRectF(0, 0, page_rect.width(), content_height))
            painter.translate(0, -page * content_height)
            doc.drawContents(painter)
            painter.restore()
            painter.drawText(
                QRectF(0, content_height, page_rect.width(), _FOOTER_HEIGHT),
                Qt.AlignRight | Qt.AlignVCenter,
                f"Page {page + 1} of {page_count}  ",
            )
    finally:
        painter.end()
    return page_count
