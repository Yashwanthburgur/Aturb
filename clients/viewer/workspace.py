"""Load a generated workspace safely.

The viewer reads a workspace that another program wrote: a `result.toml`
manifest and the artifacts it declares. Two rules shape this module.

Every declared path is resolved against the workspace root and refused unless
it stays inside it, so `..`, an absolute path and a symbolic link that escapes
the root are all refused.

A manifest from a failed generation is still a manifest. An absent or empty
artifact yields no artifact for that kind and every other field is kept, so
the viewer can show what went wrong instead of showing nothing.

A workspace that keeps a revision history is opened through its active
revision: the history names the revision, the revision holds the manifest and
the artifacts, and the outer folder stays the owner of the history. A plain
workspace is read exactly as it was before.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from aturb.agent.revisions import RevisionError, active_revision_dir, load_history

DECLARED_ARTIFACT_KINDS = ("part_file", "step_file", "native_file")
HISTORY_FILE_NAME = "history.toml"


class WorkspaceError(ValueError):
    """Raised when a workspace cannot be read safely."""


class ArtifactMissingError(WorkspaceError):
    """Raised when a declared artifact is not there.

    It is a distinct kind of ``WorkspaceError`` so that the server can answer
    an absent artifact with 404 and a refused path with 400 or 403.
    """


@dataclass(frozen=True)
class LoadedWorkspace:
    """One workspace: its root, its manifest and its declared artifacts.

    The root is the resolved workspace directory. The manifest is the parsed
    `result.toml`, with every field it holds. The artifacts hold one entry per
    declared kind: the verified path inside the root, or None when the
    manifest leaves that kind empty or absent.

    The history root is the outer folder that owns `history.toml`, and the
    active revision is the revision that history names. Both are empty for a
    plain workspace that was never edited, so every caller that builds a
    workspace by hand keeps working unchanged.
    """

    root: Path
    manifest: dict[str, Any]
    artifacts: dict[str, Path | None]
    history_root: Path | None = None
    active_revision: str | None = None

    def __post_init__(self) -> None:
        """Default the history root to the root of the workspace."""
        if self.history_root is None:
            object.__setattr__(self, "history_root", Path(self.root))


def resolve_workspace_path(root: Path, rel_path: str) -> Path:
    """Return the resolved path of a declared path inside the workspace root.

    Raises ``WorkspaceError`` when the path is empty, absolute, holds a `..`
    component, or resolves outside the root through a symbolic link.
    """
    if not isinstance(rel_path, str) or rel_path == "":
        raise WorkspaceError("the declared path is empty")
    if _is_absolute(rel_path):
        raise WorkspaceError(f"the declared path {rel_path!r} is absolute")
    if _has_parent_component(rel_path):
        raise WorkspaceError(
            f"the declared path {rel_path!r} leaves the workspace")
    try:
        resolved_root = Path(root).resolve(strict=True)
    except OSError as exc:
        raise WorkspaceError(
            f"the workspace root {root} cannot be resolved") from exc
    target = (resolved_root / rel_path).resolve(strict=False)
    if target == resolved_root or not target.is_relative_to(resolved_root):
        raise WorkspaceError(
            f"the declared path {rel_path!r} leaves the workspace")
    return target


def load_workspace(workspace_dir: Path) -> LoadedWorkspace:
    """Read the manifest of a workspace and resolve its declared artifacts.

    A workspace that keeps a `history.toml` is read through the revision the
    history names: the manifest and the artifacts come from that revision and
    the root of the loaded workspace is the revision folder. A plain workspace
    is read exactly as it was before.

    Raises ``WorkspaceError`` when the directory, the manifest, the history or
    a declared path is missing, malformed or outside the workspace.
    """
    directory = Path(workspace_dir)
    if not directory.exists():
        raise WorkspaceError(f"no workspace directory at {directory}")
    if not directory.is_dir():
        raise WorkspaceError(f"the workspace {directory} is not a directory")
    try:
        root = directory.resolve(strict=True)
    except OSError as exc:
        raise WorkspaceError(
            f"the workspace {directory} cannot be resolved") from exc
    manifest_root, active = _active_revision(root)
    manifest = _read_manifest(manifest_root / "result.toml")
    artifacts = {
        kind: _resolve_declared(manifest_root, manifest.get(kind), kind)
        for kind in DECLARED_ARTIFACT_KINDS
    }
    return LoadedWorkspace(
        root=manifest_root, manifest=manifest, artifacts=artifacts,
        history_root=root, active_revision=active)


def _active_revision(root: Path) -> tuple[Path, str | None]:
    """Return the folder to read and the active revision of a workspace.

    A workspace without a history is read as it stands. A workspace with a
    history is read through the revision the history names, and a history that
    cannot be trusted is refused.
    """
    if not (root / HISTORY_FILE_NAME).is_file():
        return root, None
    try:
        history = load_history(root)
        revision_dir = active_revision_dir(root)
    except RevisionError as exc:
        raise WorkspaceError(
            f"the history of the workspace is not usable: {exc}") from exc
    return revision_dir, history.active_revision


def resolve_artifact(workspace: LoadedWorkspace, kind: str) -> Path:
    """Return the path of one declared artifact of a loaded workspace.

    Raises ``WorkspaceError`` for an unknown kind and for a path that leaves
    the workspace, and ``ArtifactMissingError`` when the artifact is not there.
    """
    if kind not in DECLARED_ARTIFACT_KINDS:
        raise WorkspaceError(f"unknown artifact kind {kind!r}")
    target = workspace.artifacts.get(kind)
    if target is None:
        raise ArtifactMissingError(f"the workspace declares no {kind}")
    resolved = target.resolve(strict=False)
    if resolved == workspace.root or not resolved.is_relative_to(workspace.root):
        raise WorkspaceError(f"the declared {kind} leaves the workspace")
    if not resolved.is_file():
        raise ArtifactMissingError(
            f"the declared {kind} is not a file: {resolved}")
    return resolved


def _read_manifest(path: Path) -> dict[str, Any]:
    """Read and parse the manifest of a workspace."""
    if not path.is_file():
        raise WorkspaceError(f"no result.toml in the workspace {path.parent}")
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise WorkspaceError(
            f"the manifest {path} is malformed: {exc}") from exc
    except OSError as exc:
        raise WorkspaceError(
            f"the manifest {path} cannot be read: {exc}") from exc


def _resolve_declared(root: Path, value: Any, kind: str) -> Path | None:
    """Return the resolved path of one declared artifact, or None when absent."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise WorkspaceError(f"the declared {kind} is not a path")
    if value == "":
        return None
    return resolve_workspace_path(root, value)


def _is_absolute(rel_path: str) -> bool:
    """True when the path is absolute under POSIX, under Windows or locally."""
    if PurePosixPath(rel_path).is_absolute():
        return True
    windows = PureWindowsPath(rel_path)
    if windows.is_absolute() or windows.drive or windows.root:
        return True
    return Path(rel_path).is_absolute()


def _has_parent_component(rel_path: str) -> bool:
    """True when the path holds a `..` component under either separator."""
    if ".." in PurePosixPath(rel_path).parts:
        return True
    return ".." in PureWindowsPath(rel_path).parts
