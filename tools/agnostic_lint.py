"""Fail if a CAD brand name or CAD-specific term appears in the core package.

Run as a script to scan the repository:

    uv run python tools/agnostic_lint.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERN = re.compile(
    r"\b(freecad|fcstd|partdesign|sketcher|solidworks|onshape|fusion|featurescript|catia)\b",
    re.IGNORECASE,
)


def scan(core_dir: Path) -> list[tuple[str, int, str]]:
    """Return every CAD-specific term found in the .py files under core_dir.

    Each result is (path relative to core_dir with forward slashes, line
    number, line text stripped).
    """
    core_dir = Path(core_dir)
    findings: list[tuple[str, int, str]] = []
    for py_file in sorted(core_dir.rglob("*.py")):
        relative = py_file.relative_to(core_dir).as_posix()
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, start=1):
            if PATTERN.search(line):
                findings.append((relative, number, line.strip()))
    return findings


def main() -> int:
    """Scan the repository's aturb/ folder and report every finding."""
    repo_root = Path(__file__).resolve().parents[1]
    findings = scan(repo_root / "aturb")
    for relative, number, text in findings:
        print(f"{relative}:{number}: {text}")
    if findings:
        return 1
    print("agnostic_lint: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
