"""The app icon assets exist and are valid — cheap regression coverage
against "someone deletes/breaks the asset and nobody notices until the
taskbar looks wrong." Parses the PNG/ICO headers by hand rather than adding
Pillow as a project dependency just for this. See docs/plans/app-icon.md.
"""

from __future__ import annotations

import struct
from pathlib import Path

from zlog.app import _icon_path

_ASSETS = Path(__file__).resolve().parent.parent / "src" / "zlog" / "assets"

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _png_size(data: bytes) -> tuple[int, int]:
    """Width/height from the IHDR chunk (always the first chunk, right after
    the 8-byte signature + 4-byte length + 4-byte 'IHDR' tag)."""
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _ico_sizes(data: bytes) -> set[tuple[int, int]]:
    """Every (width, height) an ICONDIR's entries advertise. A 0 byte means
    256 per the ICO format (a single byte can't hold 256)."""
    _reserved, image_type, count = struct.unpack("<HHH", data[:6])
    assert image_type == 1, "not an icon (type field != 1)"
    sizes = set()
    for i in range(count):
        entry = data[6 + i * 16 : 6 + (i + 1) * 16]
        w, h = entry[0], entry[1]
        sizes.add((w or 256, h or 256))
    return sizes


def test_icon_path_resolves_to_an_existing_file():
    path = Path(_icon_path())
    assert path.is_file()
    assert path.name == "icon.png"


def test_icon_png_is_a_valid_256px_image():
    data = (_ASSETS / "icon.png").read_bytes()
    assert data.startswith(_PNG_MAGIC)
    assert _png_size(data) == (256, 256)


def test_icon_ico_is_a_valid_multi_resolution_image():
    data = (_ASSETS / "icon.ico").read_bytes()
    sizes = _ico_sizes(data)
    # Every size Windows might ask for (taskbar, Explorer list/tile/large
    # icon views) should be present, not upscaled from a single frame.
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= sizes


def test_qicon_actually_loads_the_png(qapp):
    # The stdlib PNG-header checks above prove the file is *a* valid PNG, but
    # not that Qt's own image plugin can load it — this is the exact call
    # app.main() makes, so it's the one that actually matters at runtime.
    from PySide6.QtGui import QIcon

    icon = QIcon(_icon_path())
    assert not icon.isNull()
    pixmap = icon.pixmap(32, 32)
    assert not pixmap.isNull()
    image = pixmap.toImage()
    assert any(image.pixelColor(x, image.height() // 2).alpha() > 0 for x in range(image.width()))


def test_icon_svg_source_matches_the_shipped_raster_geometry():
    svg = (_ASSETS / "icon.svg").read_text(encoding="utf-8")
    # Not a pixel comparison — just a guard that the checked-in vector source
    # (kept for future edits) hasn't drifted from the artwork actually shipped
    # in icon.png/.ico, which are generated from these exact values by hand.
    assert 'fill="#101418"' in svg
    assert 'stroke="#59c6ff"' in svg
    assert "M74 82 L138 128 L74 174" in svg
