"""Tests for the project folder jail."""

from __future__ import annotations

import pytest

from aturb.workspace.paths import PathEscapeError, resolve_inside, to_rel


def test_relative_path_resolves_inside(tmp_path):
    """A relative path inside the project resolves."""
    resolved = resolve_inside(tmp_path, "parts/a.py")

    assert resolved == (tmp_path / "parts" / "a.py").resolve()


def test_parent_path_raises(tmp_path):
    """A path that climbs out of the project is rejected."""
    with pytest.raises(PathEscapeError):
        resolve_inside(tmp_path, "../outside.py")


def test_absolute_path_outside_raises(tmp_path):
    """An absolute path outside the project is rejected."""
    outside = tmp_path.parent / "elsewhere.py"

    with pytest.raises(PathEscapeError):
        resolve_inside(tmp_path, outside)


def test_to_rel_uses_forward_slashes(tmp_path):
    """to_rel returns a relative path with forward slashes."""
    target = tmp_path / "parts" / "a.py"
    target.parent.mkdir()
    target.write_text("", encoding="utf-8")

    assert to_rel(tmp_path, target) == "parts/a.py"


def test_to_rel_outside_raises(tmp_path):
    """to_rel rejects a path outside the project."""
    with pytest.raises(PathEscapeError):
        to_rel(tmp_path, tmp_path.parent / "elsewhere.py")
