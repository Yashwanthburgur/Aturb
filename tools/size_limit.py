"""Fail fast when any Python file grows past the line limit.

Run as a script to scan the repository:

    uv run python tools/size_limit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

LIMIT = 300  # starting default
SCANNED = ["aturb", "packs", "tools", "tests", "clients"]


def find_oversized(
    root: Path,
    limit: int = LIMIT,
) -> list[tuple[str, int]]:
    """Return every .py file under the scanned folders with more than limit lines.

    Each result is (path relative to root using forward slashes, line count).
    Missing scanned folders are skipped.
    """
    offenders: list[tuple[str, int]] = []
    for folder in SCANNED:
        folder_path = root / folder
        if not folder_path.is_dir():
            continue
        for py_file in sorted(folder_path.rglob("*.py")):
            if not py_file.is_file():
                continue
            count = len(py_file.read_text(encoding="utf-8").splitlines())
            if count > limit:
                relative = py_file.relative_to(root).as_posix()
                offenders.append((relative, count))
    return offenders


def main() -> int:
    """Scan the repository root (the parent of tools/) and report offenders."""
    repo_root = Path(__file__).resolve().parents[1]
    offenders = find_oversized(repo_root)
    if offenders:
        for relative, count in offenders:
            print(f"{relative}: {count} lines")
        return 1
    print("size_limit: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
