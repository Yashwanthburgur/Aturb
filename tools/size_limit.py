"""Check the Python file sizes against the soft guideline and the hard ceiling.

Run as a script to scan the repository:

    uv run python tools/size_limit.py

The policy has two tiers. A file above the soft guideline of 300 lines prints a
warning and the script still exits 0, because a long file is a cohesion smell
rather than a broken build. A file above the hard ceiling of 500 lines prints a
failure and the script exits 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

SOFT_LIMIT = 300  # starting default
HARD_LIMIT = 500  # starting default
SCANNED = ["aturb", "packs", "tools", "tests", "clients"]


def scan_files(root: Path) -> list[tuple[str, int]]:
    """Return every scanned .py file with its line count.

    Each result is (path relative to root using forward slashes, line count).
    Missing scanned folders are skipped.
    """
    files: list[tuple[str, int]] = []
    for folder in SCANNED:
        folder_path = root / folder
        if not folder_path.is_dir():
            continue
        for py_file in sorted(folder_path.rglob("*.py")):
            if not py_file.is_file():
                continue
            count = len(py_file.read_text(encoding="utf-8").splitlines())
            relative = py_file.relative_to(root).as_posix()
            files.append((relative, count))
    return files


def find_oversized(
    root: Path,
    limit: int = SOFT_LIMIT,
) -> list[tuple[str, int]]:
    """Return every .py file under the scanned folders with more than limit lines.

    Each result is (path relative to root using forward slashes, line count).
    Missing scanned folders are skipped.
    """
    return [(relative, count) for relative, count in scan_files(root)
            if count > limit]


def main(root: Path | None = None) -> int:
    """Scan the repository and report the soft warnings and the hard failures."""
    if root is None:
        repo_root = Path(__file__).resolve().parents[1]
    else:
        repo_root = Path(root)
    files = scan_files(repo_root)
    warnings = [(relative, count) for relative, count in files
                if SOFT_LIMIT < count <= HARD_LIMIT]
    failures = [(relative, count) for relative, count in files
                if count > HARD_LIMIT]
    for relative, count in warnings:
        print(f"WARNING: {relative} has {count} lines "
              f"(soft guideline: {SOFT_LIMIT})")
    for relative, count in failures:
        print(
            f"FAIL: {relative} has {count} lines (hard ceiling: {HARD_LIMIT})")
    if failures:
        print(
            f"size_limit: FAILED ({len(failures)} file(s) above the hard ceiling)")
        return 1
    if warnings:
        print(
            f"size_limit: OK with {len(warnings)} warning(s) above the soft guideline")
        return 0
    print("size_limit: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
