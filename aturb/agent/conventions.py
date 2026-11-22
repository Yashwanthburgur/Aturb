"""The project conventions of a part file, and the checker of the ones text can show.

The conventions are C1 to C6 of docs/CONVENTIONS.md. This module holds the text
the prompt carries and the checker of the rules that can be checked from the text
of a file without a CAD. C4 and C6 are judged by the neutral checks and by the
evaluation, not by the checker.

The checker is advisory. It returns one finding per broken rule and never
raises for a broken rule, so a caller can report the findings and carry on.
Nothing here blocks a build, and nothing here names a CAD.

The part file is read as text. It is never parsed as code and never executed,
so a part file in any language is read the same way.
"""

from __future__ import annotations

import re

# The text of the conventions that the prompt carries. It names the rules C1 to
# C6, so the document, the checker and the prompt cannot drift apart.
CONVENTIONS_TEXT = """\
Project conventions. Follow these six rules in the part file you write.
C1 part identity: the part file is named <part_id>_<name><extension>; the part ID is the identity.
C2 parameter block: the dimensions are named constants at the top of the file, in a
    marked block, and every constant name ends with `_MM`. Mark the block with the
    comments `# --- PARAMS ---` and `# --- END PARAMS ---`.
C3 units: every length is in millimetres, and the file says so.
C4 placement: the part is centred on the origin in X and Y and spans Z = 0 to its
    thickness.
C5 no machine values: no absolute path, no drive letter and no machine-specific
    value in the file.
C6 expectations are authoritative: the expectation file is input and is not changed
    by the agent without a declared reason.
"""

# The parameter-block markers of the demo part, unchanged.
PARAM_START = "# --- PARAMS ---"
PARAM_END = "# --- END PARAMS ---"

DRIVE_LETTER_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]")
UNC_PATH_RE = re.compile(r"\\\\[A-Za-z0-9_.-]+")
ABSOLUTE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_:])/[A-Za-z][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_.-]+)*")
MILLIMETRE_RE = re.compile(
    r"\b(?:millimetres?|millimeters?|mm)\b", re.IGNORECASE)
UNIT_WORD_RE = re.compile(
    r"\b(?:units?|lengths?|dimensions?|sizes?)\b", re.IGNORECASE)
ASSIGNMENT_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)\s*(?::[^=]+)?=")
STRING_RE = re.compile(
    r"'''.*?'''|\"\"\".*?\"\"\"|'[^'\n]*'|\"[^\"\n]*\"", re.DOTALL)


def conventions_text() -> str:
    """Return the text of the project conventions that the prompt carries.

    The text is fixed and names the rules C1 to C6 of docs/CONVENTIONS.md, so the
    document, the checker and the prompt cannot drift apart. The same text comes
    back on every call: it depends on nothing but this module.
    """
    return CONVENTIONS_TEXT


def check_conventions(part_id: str, extension: str, text: str) -> list[str]:
    """Return one finding per convention the part file breaks.

    The findings name the convention they break and say what is wrong. A broken
    convention is a finding, never an exception: the checker never raises for a
    part file it does not like, and an empty list means the file follows every
    rule that can be checked from its text.
    """
    findings: list[str] = []
    findings.extend(_check_part_identity(part_id, extension))
    findings.extend(_check_parameter_block(text))
    findings.extend(_check_units(text))
    findings.extend(_check_machine_values(text))
    return findings


def _check_part_identity(part_id: str, extension: str) -> list[str]:
    """C1: the part file is named <part_id>_<name><extension>.

    The part ID and the extension are what the project layout gives the part,
    so the check is on the file name they produce. The part ID has to be the
    first segment of that name, or it is not the identity of the part.
    """
    findings: list[str] = []
    if not part_id:
        findings.append("C1: the part ID is empty, so the part file cannot be named "
                        "<part_id>_<name><extension>")
    elif "/" in part_id or "\\" in part_id:
        findings.append(
            f"C1: the part ID {part_id!r} is not a single file name segment")
    elif "_" in part_id:
        findings.append(f"C1: the part ID {part_id!r} holds an underscore, so it is not "
                        "the first segment of the file name <part_id>_<name><extension>")
    if not extension:
        findings.append(
            "C1: the extension is empty, so the part file has no extension")
    elif not extension.startswith("."):
        findings.append(
            f"C1: the extension {extension!r} does not start with a dot")
    return findings


def _marker_line(lines: list[str], marker: str) -> int | None:
    """Return the 1-based line of the marker, or None when it is absent."""
    for number, line in enumerate(lines, start=1):
        if line.strip() == marker:
            return number
    return None


def _keep_line_numbers(match: re.Match[str]) -> str:
    """Return the newlines of a matched literal, so the line numbers stay."""
    return "\n" * match.group(0).count("\n")


def _first_code_line(text: str) -> int | None:
    """Return the 1-based number of the first line that holds code.

    String literals and comments are removed first, so what is left is the code
    of the file. The scan is textual: the file is never parsed, so a part file
    in any language is read the same way.
    """
    without_literals = STRING_RE.sub(_keep_line_numbers, text)
    for number, line in enumerate(without_literals.splitlines(), start=1):
        if line.split("#", 1)[0].strip():
            return number
    return None


def _check_parameter_block(text: str) -> list[str]:
    """C2: a marked parameter block at the top, with constants named *_MM."""
    lines = text.splitlines()
    start = _marker_line(lines, PARAM_START)
    end = _marker_line(lines, PARAM_END)
    if start is None or end is None:
        missing = PARAM_START if start is None else PARAM_END
        return [f"C2: the parameter block marker {missing!r} is missing"]
    if end < start:
        return [f"C2: the marker {PARAM_END!r} comes before {PARAM_START!r}"]
    findings: list[str] = []
    first = _first_code_line(text)
    if first is not None and start > first:
        findings.append(f"C2: line {start}: the parameter block is not at the top "
                        "of the file")
    names: list[tuple[int, str]] = []
    for number in range(start + 1, end):
        match = ASSIGNMENT_RE.match(lines[number - 1])
        if match:
            names.extend((number, name.strip())
                         for name in match.group(1).split(","))
    if not names:
        findings.append(
            f"C2: line {start}: the parameter block declares no named constant")
    for number, name in names:
        if not name.endswith("_MM"):
            findings.append(f"C2: line {number}: the parameter constant {name!r} "
                            "does not end with '_MM'")
    return findings


def _check_units(text: str) -> list[str]:
    """C3: the file states that lengths are in millimetres."""
    for line in text.splitlines():
        if MILLIMETRE_RE.search(line) and UNIT_WORD_RE.search(line):
            return []
    return ["C3: the file does not state that lengths are in millimetres"]


def _check_machine_values(text: str) -> list[str]:
    """C5: no absolute path and no drive-letter path in the file."""
    findings: list[str] = []
    patterns = ((DRIVE_LETTER_RE, "drive-letter path"),
                (UNC_PATH_RE, "UNC path"),
                (ABSOLUTE_PATH_RE, "absolute path"))
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern, label in patterns:
            for match in pattern.finditer(line):
                findings.append(f"C5: line {number}: the {label} {match.group(0)!r} "
                                "is a machine value")
    return findings
