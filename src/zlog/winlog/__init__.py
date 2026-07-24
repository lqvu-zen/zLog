"""Windows-only log sources (peer of ``zlog.adb``).

Currently: capturing an app's ``OutputDebugString`` stream from the system DBWIN
buffer. Everything OS-specific is imported lazily inside the reader thread, so
this package imports safely on any platform; the pure parsing/mapping lives in
``zlog.core.dbwin``.
"""
