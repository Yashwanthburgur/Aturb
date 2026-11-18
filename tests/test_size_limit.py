"""Tests for the file size limit tool."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from size_limit import find_oversized  # noqa: E402


def _write_lines(path: Path, count: int) -> None:
    """Write a file with exactly count lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"line {i}" for i in range(
        count)) + "\n", encoding="utf-8")


def test_oversized_file_is_reported(tmp_path: Path) -> None:
    """A 301-line file is reported as oversized."""
    target = tmp_path / "aturb" / "big.py"
    _write_lines(target, 301)

    offenders = find_oversized(tmp_path)

    assert ("aturb/big.py", 301) in offenders


def test_file_at_limit_is_not_reported(tmp_path: Path) -> None:
    """A 300-line file is within the limit."""
    target = tmp_path / "aturb" / "exact.py"
    _write_lines(target, 300)

    offenders = find_oversized(tmp_path)

    assert ("aturb/exact.py", 300) not in offenders


def test_missing_scanned_folder_does_not_raise(tmp_path: Path) -> None:
    """A missing scanned folder is skipped instead of raising."""
    assert not (tmp_path / "aturb").exists()

    offenders = find_oversized(tmp_path)

    assert offenders == []
