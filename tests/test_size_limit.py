"""Tests for the file size limit tool."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from size_limit import HARD_LIMIT, SOFT_LIMIT, find_oversized, main  # noqa: E402


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


def test_a_file_at_the_soft_limit_passes(tmp_path: Path, capsys) -> None:
    """A file at the soft guideline passes and prints the OK line."""
    _write_lines(tmp_path / "aturb" / "exact.py", SOFT_LIMIT)

    code = main(tmp_path)

    assert code == 0
    assert "size_limit: OK" in capsys.readouterr().out


def test_a_file_above_the_soft_limit_warns_and_passes(
        tmp_path: Path, capsys) -> None:
    """A file above the soft guideline warns and still exits 0."""
    _write_lines(tmp_path / "aturb" / "long.py", SOFT_LIMIT + 1)

    code = main(tmp_path)

    out = capsys.readouterr().out
    assert code == 0
    assert (f"WARNING: aturb/long.py has {SOFT_LIMIT + 1} lines "
            f"(soft guideline: {SOFT_LIMIT})") in out


def test_a_file_at_the_hard_limit_only_warns(tmp_path: Path, capsys) -> None:
    """A file exactly at the hard ceiling is a warning, not a failure."""
    _write_lines(tmp_path / "aturb" / "edge.py", HARD_LIMIT)

    code = main(tmp_path)

    out = capsys.readouterr().out
    assert code == 0
    assert "WARNING: aturb/edge.py" in out
    assert "FAIL" not in out


def test_a_file_above_the_hard_limit_fails(tmp_path: Path, capsys) -> None:
    """A file above the hard ceiling fails with exit code 1."""
    _write_lines(tmp_path / "aturb" / "huge.py", HARD_LIMIT + 1)

    code = main(tmp_path)

    out = capsys.readouterr().out
    assert code == 1
    assert "FAIL: aturb/huge.py" in out
