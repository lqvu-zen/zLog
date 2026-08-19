"""Deobfuscate a ProGuard/R8 `mapping.txt` against Java/Kotlin stack trace
lines — pure text substitution, no Qt, no I/O (the caller reads the file).

`mapping.txt` shape (ProGuard and R8 agree on this format):

    com.example.app.MainActivity -> com.example.app.a:
        void onCreate(android.os.Bundle) -> a
        23:27:void onClick(android.view.View) -> b

Class lines start at column 0: `<original> -> <obfuscated>:`. Member lines are
indented and belong to the most recently seen class line. An optional
`start:end:` prefix on a member line is the line range **in the obfuscated
build's own line-number table** that this member covers — the number that
actually shows up in a captured `(File:N)` trace, which is what disambiguates
overloaded methods that share an obfuscated name.

Unmapped names are never guessed — passed through unchanged, same rule as
`core/logformat.py`'s `apply_aliases`. A wrong-but-confident name is worse
than an obviously-untranslated one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_CLASS_RE = re.compile(r"^(\S+) -> (\S+):\s*$")
_MEMBER_RE = re.compile(
    r"^\s+(?:(\d+):(\d+):)?\S+\s+(\w+)\([^)]*\)(?::\d+(?::\d+)?)?\s*->\s*(\S+)\s*$"
)
# `at <class>.<member>(<file>:<line>)` — the file is usually "SourceFile" or
# similar post-obfuscation, and gets rewritten to the real simple class name.
_FRAME_RE = re.compile(r"^(\s*at\s+)([\w$.]+)\.(\w+)\(([^:)]*)(?::(\d+))?\)(.*)$")
# A bare exception header / "Caused by:" line naming a fully-qualified class.
_HEADER_RE = re.compile(r"^((?:Caused by:\s*)?)([\w$.]+)(: .*)?$")


@dataclass(frozen=True, slots=True)
class MemberMapping:
    obfuscated_name: str
    original_name: str
    start_line: int | None
    end_line: int | None

    def covers(self, line: int | None) -> bool:
        if self.start_line is None or self.end_line is None or line is None:
            return False
        return self.start_line <= line <= self.end_line


@dataclass(slots=True)
class ProguardMapping:
    # obfuscated class name -> original class name
    classes: dict[str, str] = field(default_factory=dict)
    # obfuscated class name -> its members, in file order
    members: dict[str, list[MemberMapping]] = field(default_factory=dict)

    def deobfuscate_class(self, name: str) -> str:
        return self.classes.get(name, name)

    def deobfuscate_member(self, obf_class: str, obf_member: str, line: int | None) -> str:
        candidates = [m for m in self.members.get(obf_class, ()) if m.obfuscated_name == obf_member]
        if not candidates:
            return obf_member
        for m in candidates:
            if m.covers(line):
                return m.original_name
        # No line info, or none of the ranged candidates cover it: best guess
        # is the first one — a plausible name beats an obfuscated one, even
        # when overload disambiguation isn't possible (documented limitation,
        # see docs/plans/crash-symbolication.md).
        return candidates[0].original_name

    def simple_name(self, original_class: str) -> str:
        """The source file's base name for `original_class` — a nested class
        (`Outer$Inner`) is defined in its *enclosing* class's file, so this
        takes the part before the first `$`, not the innermost segment."""
        simple = original_class.rsplit(".", 1)[-1]
        return simple.split("$", 1)[0]


def parse_mapping(text: str) -> ProguardMapping:
    mapping = ProguardMapping()
    current_obf: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        if raw_line[0] not in (" ", "\t"):
            m = _CLASS_RE.match(raw_line)
            if m:
                original, obfuscated = m.group(1), m.group(2)
                mapping.classes[obfuscated] = original
                mapping.members.setdefault(obfuscated, [])
                current_obf = obfuscated
            else:
                current_obf = None
            continue
        if current_obf is None:
            continue
        m = _MEMBER_RE.match(raw_line)
        if not m:
            continue
        start, end, name, obf_name = m.groups()
        mapping.members[current_obf].append(
            MemberMapping(
                obfuscated_name=obf_name,
                original_name=name,
                start_line=int(start) if start else None,
                end_line=int(end) if end else None,
            )
        )
    return mapping


def deobfuscate_line(mapping: ProguardMapping, message: str) -> str:
    """Rewrite one message line: a stack frame, an exception header, or
    neither (passed through byte-for-byte)."""
    m = _FRAME_RE.match(message)
    if m:
        prefix, obf_class, obf_member, file_part, line_part, rest = m.groups()
        if obf_class not in mapping.classes:
            return message
        original_class = mapping.deobfuscate_class(obf_class)
        line_no = int(line_part) if line_part else None
        original_member = mapping.deobfuscate_member(obf_class, obf_member, line_no)
        file_out = mapping.simple_name(original_class) + _guess_ext(file_part)
        loc = f"{file_out}:{line_part}" if line_part else file_out
        return f"{prefix}{original_class}.{original_member}({loc}){rest}"

    m = _HEADER_RE.match(message)
    if m and m.group(2) in mapping.classes:
        caused_by, obf_class, tail = m.groups()
        return f"{caused_by}{mapping.deobfuscate_class(obf_class)}{tail or ''}"

    return message


def _guess_ext(original_file_part: str) -> str:
    """Preserve a real extension (`Foo.kt`) if the captured file name had
    one. ProGuard/R8's common `-renamesourcefileattribute SourceFile` setup
    replaces it with the literal placeholder `SourceFile`, which carries no
    extension — rather than assume `.java` (wrong for a Kotlin class), leave
    it off entirely; the simple class name alone is still identifiable, and
    this is a display label, not something anything parses further."""
    if "." in original_file_part:
        return "." + original_file_part.rsplit(".", 1)[-1]
    return ""
