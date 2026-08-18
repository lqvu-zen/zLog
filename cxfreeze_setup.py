"""cx_Freeze build script for the zLog Windows executable.

Usage (from the project root, ideally on Windows):

    uv run --extra build python cxfreeze_setup.py build
    # or double-click build.bat

Output:
    build/exe.win-amd64-<pyver>/zlog.exe   (with its bundled runtime)

`gui` base means no console window. cx_Freeze ships a PySide6 hook, so the Qt
plugins/libraries are pulled in automatically.
"""

from __future__ import annotations

import sys

from cx_Freeze import Executable, setup

from zlog import __version__

base = "gui" if sys.platform == "win32" else None

build_exe_options = {
    "packages": ["zlog"],
    "excludes": ["tkinter", "unittest", "test", "pydoc_data"],
    "include_msvcr": True,  # bundle the MSVC runtime so it runs on a clean Windows
    # cx_Freeze's module finder only follows imports, so a package's own
    # non-.py data files (the app icon) need to be listed explicitly or the
    # frozen build won't have them at the path app._icon_path() resolves to.
    "include_files": [("src/zlog/assets", "lib/zlog/assets")],
}

setup(
    name="zlog",
    version=__version__,
    description="A live log viewer for Android devices, Windows apps, and log files.",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "src/zlog/__main__.py",
            base=base,
            target_name="zlog",
            icon="src/zlog/assets/icon.ico",
        )
    ],
)
