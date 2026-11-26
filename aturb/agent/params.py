"""Read the parameter block of a part file as structured entries.

A part file may mark its named constants with a block:

    # --- PARAMS ---
    LENGTH_MM = 120.0  # the length of the plate
    WIDTH_MM = 60.0
    # --- END PARAMS ---

The extractor reads that block as text. It never parses the file as code and
never executes it, so a part file in any language is read the same way. Only
the top-level assignments of the block are read: a blank line, a comment-only
line and an indented line hold no parameter and are left out.

The module is CAD-neutral: it knows about markers, names, values and comments,
and about nothing else.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

PARAM_START = "# --- PARAMS ---"
PARAM_END = "# --- END PARAMS ---"

ASSIGNMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


@dataclass(frozen=True)
class ParamEntry:
    """One named constant of the parameter block of a part file.

    The value is the text of the right-hand side and the comment is the
    optional inline comment, without its marker.
    """

    name: str
    value: str
    comment: str = ""


def extract_params(source: str) -> tuple[ParamEntry, ...]:
    """Return the named constants of the parameter block of a source.

    The result is empty when the markers are absent, when they come in the
    wrong order or when the block holds no assignment.
    """
    lines = source.splitlines()
    start = _marker(lines, PARAM_START)
    end = _marker(lines, PARAM_END)
    if start is None or end is None or end < start:
        return ()
    entries: list[ParamEntry] = []
    for line in lines[start + 1:end]:
        entry = _entry(line)
        if entry is not None:
            entries.append(entry)
    return tuple(entries)


def format_params_block(params: Sequence[ParamEntry]) -> str:
    """Return the compact block of the current parameters of a part.

    The block is empty when there is no parameter to show.
    """
    if not params:
        return ""
    lines = ["Current parameters:"]
    for param in params:
        text = f"- {param.name} = {param.value}"
        if param.comment:
            text += f" ({param.comment})"
        lines.append(text)
    return "\n".join(lines)


def _marker(lines: list[str], marker: str) -> int | None:
    """Return the index of the marker line, or None when it is absent."""
    for index, line in enumerate(lines):
        if line.strip() == marker:
            return index
    return None


def _entry(line: str) -> ParamEntry | None:
    """Return the entry of one line of the block, or None when it holds none."""
    if line[:1].isspace():
        return None
    match = ASSIGNMENT_RE.match(line)
    if match is None:
        return None
    value, comment = _split_comment(match.group(2))
    if not value:
        return None
    return ParamEntry(name=match.group(1), value=value, comment=comment)


def _split_comment(text: str) -> tuple[str, str]:
    """Split the value of an assignment from its inline comment.

    A marker inside a quoted value is part of the value, so the quotes are
    followed while the comment is looked for.
    """
    quote = ""
    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#":
            return text[:index].strip(), text[index + 1:].strip()
    return text.strip(), ""
