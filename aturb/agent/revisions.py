"""The immutable revision history of an editable workspace.

A workspace that can be edited keeps its history in ``history.toml`` and its
revisions in ``revisions/rNNNN/``. Every revision folder is a complete
standalone workspace: a ``result.toml`` manifest and a ``project/`` folder.
A revision is never rewritten, and the history is written atomically.
"""

from __future__ import annotations

import re
import shutil
import tomllib
from dataclasses import asdict, dataclass, replace
from pathlib import Path, PurePosixPath, PureWindowsPath

from aturb.agent.record import toml_string
from aturb.workspace.io import atomic_write_text
from aturb.workspace.paths import PathEscapeError, resolve_inside

HISTORY_FILE_NAME = "history.toml"
REVISIONS_DIR_NAME = "revisions"
MANIFEST_FILE_NAME = "result.toml"
PROJECT_DIR_NAME = "project"
INITIAL_REVISION_ID = "r0001"  # starting default
REVISION_ID_WIDTH = 4  # starting default
REVISION_ID_RE = re.compile(r"^r[0-9]{4,}$")
KINDS = ("initial", "edit")
STATUSES = ("ok", "error")
ENTRY_KEYS = ("id", "parent", "kind", "status", "stop_reason", "instruction",
              "attempts", "prompt_version", "rel_dir")


class RevisionError(ValueError):
    """Raised when a revision history cannot be read, written or trusted."""


@dataclass(frozen=True)
class RevisionEntry:
    """One revision of a workspace history, with its folder relative to it."""

    id: str
    parent: str
    kind: str
    status: str
    stop_reason: str
    instruction: str
    attempts: int
    prompt_version: str
    rel_dir: str


@dataclass(frozen=True)
class WorkspaceHistory:
    """The history of a workspace: the active revision and every revision."""

    active_revision: str
    revisions: tuple[RevisionEntry, ...]


def is_verified_manifest(manifest: dict, revision_dir: Path | None = None) -> bool:
    """True when a manifest describes a verified single solid."""
    if not isinstance(manifest, dict):
        return False
    if (manifest.get("status") != "ok" or manifest.get("is_valid") is not True
            or manifest.get("is_single_solid") is not True):
        return False
    part_file = manifest.get("part_file")
    if not isinstance(part_file, str) or not _is_safe_relative(part_file):
        return False
    if revision_dir is None:
        return True
    try:
        target = resolve_inside(Path(revision_dir), part_file)
    except (PathEscapeError, OSError, ValueError):
        return False
    return target.is_file()


def read_manifest(path: Path) -> dict:
    """Read the manifest of a workspace and return the table it holds."""
    try:
        with Path(path).open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RevisionError(
            f"the manifest at {path} is unreadable: {exc}") from exc


def ensure_history(workspace: Path) -> WorkspaceHistory:
    """Return the history of a workspace, bootstrapping it when it has none.

    A workspace without a history is bootstrapped from its verified manifest.
    """
    workspace = Path(workspace)
    if (workspace / HISTORY_FILE_NAME).exists():
        return load_history(workspace)
    manifest = read_manifest(workspace / MANIFEST_FILE_NAME)
    if not is_verified_manifest(manifest, workspace):
        raise RevisionError(
            "the workspace holds no verified part; a failed generation is never editable")
    revision_dir = workspace / REVISIONS_DIR_NAME / INITIAL_REVISION_ID
    _snapshot(workspace, revision_dir)
    entry = RevisionEntry(
        id=INITIAL_REVISION_ID, parent="", kind="initial", status="ok",
        stop_reason=str(manifest.get("stop_reason", "")), instruction="",
        attempts=_count(manifest.get("attempts", 0)),
        prompt_version=str(manifest.get("prompt_version", "")),
        rel_dir=revision_dir.resolve().relative_to(workspace.resolve()).as_posix())
    history = WorkspaceHistory(
        active_revision=INITIAL_REVISION_ID, revisions=(entry,))
    write_history(workspace, history)
    return history


def load_history(workspace: Path) -> WorkspaceHistory:
    """Read the history of a workspace and check every path it names."""
    workspace = Path(workspace)
    path = workspace / HISTORY_FILE_NAME
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RevisionError(
            f"the history of the workspace is unreadable: {exc}") from exc
    active = raw.get("active_revision")
    records = raw.get("revisions", [])
    if not isinstance(active, str) or not active:
        raise RevisionError("the history names no active revision")
    if not isinstance(records, list):
        raise RevisionError("the revisions of the history are not a list")
    entries = tuple(_entry(record, workspace) for record in records)
    if not entries:
        raise RevisionError("the history holds no revision")
    if active not in {entry.id for entry in entries}:
        raise RevisionError(
            f"the active revision {active!r} is not in the history")
    return WorkspaceHistory(active_revision=active, revisions=entries)


def write_history(workspace: Path, history: WorkspaceHistory) -> Path:
    """Write the history of a workspace atomically and return its path."""
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    lines = [f"active_revision = {toml_string(history.active_revision)}", ""]
    for entry in history.revisions:
        lines.append("[[revisions]]")
        for key, value in asdict(entry).items():
            lines.append(f"{key} = {int(value)}" if isinstance(value, int)
                         else f"{key} = {toml_string(str(value))}")
        lines.append("")
    path = workspace / HISTORY_FILE_NAME
    _atomic_write(path, "\n".join(lines))
    return path


def next_revision_id(workspace: Path, history: WorkspaceHistory) -> str:
    """Return the next free revision id, counting the folders on disk too."""
    ids = [entry.id for entry in history.revisions]
    folder = Path(workspace) / REVISIONS_DIR_NAME
    if folder.is_dir():
        ids += [child.name for child in folder.iterdir() if child.is_dir()]
    highest = max((_number(name) for name in ids), default=0)
    return f"r{highest + 1:0{REVISION_ID_WIDTH}d}"


def active_revision_dir(workspace: Path) -> Path:
    """Return the folder of the active revision of a workspace."""
    workspace = Path(workspace)
    history = load_history(workspace)
    return _revision_dir(workspace, _find(history, history.active_revision).rel_dir)


def rollback_revision(workspace: Path, revision_id: str) -> WorkspaceHistory:
    """Make a verified revision the active one and keep every later revision."""
    workspace = Path(workspace)
    history = load_history(workspace)
    entry = _find(history, revision_id)
    if entry.status != "ok":
        raise RevisionError(
            f"the revision {revision_id!r} is not a verified revision")
    folder = _revision_dir(workspace, entry.rel_dir)
    manifest = read_manifest(folder / MANIFEST_FILE_NAME)
    if not is_verified_manifest(manifest, folder):
        raise RevisionError(
            f"the revision {revision_id!r} holds no verified part")
    updated = replace(history, active_revision=revision_id)
    write_history(workspace, updated)
    return updated


def _entry(record: dict, workspace: Path) -> RevisionEntry:
    """Build one revision entry from one table of the history."""
    if not isinstance(record, dict):
        raise RevisionError("a revision of the history is not a table")
    missing = [key for key in ENTRY_KEYS if key not in record]
    if missing:
        raise RevisionError(
            f"a revision of the history is missing key(s): {', '.join(missing)}")
    kind = record["kind"]
    status = record["status"]
    if kind not in KINDS:
        raise RevisionError(f"unknown revision kind {kind!r}")
    if status not in STATUSES:
        raise RevisionError(f"unknown revision status {status!r}")
    rel_dir = record["rel_dir"]
    if not isinstance(rel_dir, str):
        raise RevisionError("the folder of a revision is not text")
    _revision_dir(workspace, rel_dir)
    return RevisionEntry(
        id=str(record["id"]), parent=str(record["parent"]), kind=kind,
        status=status, stop_reason=str(record["stop_reason"]),
        instruction=str(record["instruction"]), attempts=_count(record["attempts"]),
        prompt_version=str(record["prompt_version"]), rel_dir=rel_dir)


def _find(history: WorkspaceHistory, revision_id: str) -> RevisionEntry:
    """Return one recorded revision, or raise when it is not recorded."""
    for entry in history.revisions:
        if entry.id == revision_id:
            return entry
    raise RevisionError(f"the revision {revision_id!r} is not in the history")


def _revision_dir(workspace: Path, rel_dir: str) -> Path:
    """Return the folder of a revision, refusing any path that escapes."""
    if not isinstance(rel_dir, str) or not rel_dir.strip():
        raise RevisionError("a revision names no folder")
    if not _is_safe_relative(rel_dir):
        raise RevisionError(
            f"the revision folder {rel_dir!r} is not a safe relative path")
    try:
        target = resolve_inside(Path(workspace), rel_dir)
    except (PathEscapeError, OSError, ValueError) as exc:
        raise RevisionError(
            f"the revision folder {rel_dir!r} leaves the workspace") from exc
    if target == Path(workspace).resolve():
        raise RevisionError(
            "a revision folder may not be the workspace itself")
    return target


def _is_safe_relative(rel: str) -> bool:
    """True when a path is relative and holds no parent component."""
    if not rel.strip():
        return False
    posix = PurePosixPath(rel)
    windows = PureWindowsPath(rel)
    if (posix.is_absolute() or windows.is_absolute() or windows.drive
            or windows.root or Path(rel).is_absolute()):
        return False
    return ".." not in posix.parts and ".." not in windows.parts


def _snapshot(workspace: Path, revision_dir: Path) -> None:
    """Copy the manifest and the project of a workspace into a revision."""
    if revision_dir.exists():
        shutil.rmtree(revision_dir)
    revision_dir.mkdir(parents=True)
    shutil.copy2(workspace / MANIFEST_FILE_NAME,
                 revision_dir / MANIFEST_FILE_NAME)
    project = workspace / PROJECT_DIR_NAME
    if project.is_dir():
        shutil.copytree(project, revision_dir / PROJECT_DIR_NAME)


def _atomic_write(path: Path, text: str) -> None:
    """Write a text to a file atomically, through the shared helper."""
    atomic_write_text(path, text)


def _count(value: object) -> int:
    """Return a count of a manifest, or zero when it holds none."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _number(revision_id: str) -> int:
    """Return the number of a revision id, or zero when it holds none."""
    if not REVISION_ID_RE.fullmatch(revision_id):
        return 0
    return int(revision_id[1:])
