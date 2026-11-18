"""Keep every path inside the project folder."""

from __future__ import annotations

from pathlib import Path


class PathEscapeError(Exception):
    """Raised when a path points outside the project folder."""


def resolve_inside(root: Path, rel: str | Path) -> Path:
    """Return the resolved path of rel inside root.

    Raises PathEscapeError when the result would leave root.
    """
    root_resolved = Path(root).resolve()
    candidate = (root_resolved / rel).resolve()
    if not candidate.is_relative_to(root_resolved):
        raise PathEscapeError(f"{candidate} is outside {root_resolved}")
    return candidate


def to_rel(root: Path, path: Path) -> str:
    """Return path relative to root, with forward slashes.

    Raises PathEscapeError when path is outside root.
    """
    root_resolved = Path(root).resolve()
    candidate = Path(path).resolve()
    if not candidate.is_relative_to(root_resolved):
        raise PathEscapeError(f"{candidate} is outside {root_resolved}")
    return candidate.relative_to(root_resolved).as_posix()
