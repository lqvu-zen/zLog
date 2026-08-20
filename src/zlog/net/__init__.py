"""Network log sources (peer of ``zlog.adb``/``zlog.winlog``).

Currently: a TCP listener that accepts a newline-delimited text stream from any
process that can open a socket. Cross-platform (plain ``socket``), so it needs
no OS-specific imports.
"""
