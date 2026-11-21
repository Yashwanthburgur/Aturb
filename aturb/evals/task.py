"""Read the task file of one task folder and refuse a file that cannot be trusted.

A task is a folder with a task file, an answer file and its own project. The
task file holds the metadata of the task: the task ID, the part ID the task
builds, a name and a description.

The task ID and the part ID are two different things. The task ID names the
task and must equal the name of the task folder. The part ID names the part the
task builds; it is never derived from the task ID and never falls back to it.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from aturb.workspace.paths import PathEscapeError, resolve_inside

TASK_FILE_NAME = "task.toml"

REQUIRED_KEYS = ("task_id", "part_id", "name", "description")

PART_ID_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789_-"
)


@dataclass(frozen=True)
class TaskSpec:
    """What the task file of one task says.

    ``task_id`` names the task and ``part_id`` names the part the task builds.
    The two are separate values and may differ.
    """

    task_id: str
    part_id: str
    name: str
    description: str


def load_task(task_dir: Path) -> TaskSpec:
    """Load the task file of one task folder.

    The task file is ``<task_dir>/task.toml``, resolved inside the task folder.
    A missing file raises ``FileNotFoundError``. A file that is not valid TOML,
    that misses a key, that holds an unknown key, that holds a value of the
    wrong type, whose ``task_id`` is not the folder name, or whose ``part_id``
    is not a plain token raises ``ValueError``.
    """
    task_dir = Path(task_dir)
    path = _task_file(task_dir)
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc
    return _spec(raw, task_dir, path)


def _task_file(task_dir: Path) -> Path:
    """Return the task file of a task folder, resolved inside that folder."""
    try:
        return resolve_inside(task_dir, TASK_FILE_NAME)
    except PathEscapeError as exc:
        raise ValueError(
            f"the task file is outside the task folder: {exc}") from exc


def _spec(raw: dict, task_dir: Path, path: Path) -> TaskSpec:
    """Check the task file and return the task it describes."""
    missing = [key for key in REQUIRED_KEYS if key not in raw]
    if missing:
        raise ValueError(
            f"task file {path} is missing key(s): {', '.join(missing)}")
    unknown = sorted(set(raw) - set(REQUIRED_KEYS))
    if unknown:
        raise ValueError(
            f"task file {path} has unknown key(s): {', '.join(unknown)}")

    values = {key: _text(raw[key], key) for key in REQUIRED_KEYS}
    folder = task_dir.name
    if values["task_id"] != folder:
        raise ValueError(
            f"task_id {values['task_id']!r} does not match the task folder "
            f"{folder!r}")
    part_id = values["part_id"]
    if not _is_plain_token(part_id):
        raise ValueError(
            f"part_id {part_id!r} is not a plain token; it may hold letters, "
            "digits, '_' and '-' only")
    return TaskSpec(
        task_id=values["task_id"],
        part_id=part_id,
        name=values["name"],
        description=values["description"],
    )


def _text(value, key: str) -> str:
    """Return a value as text, or raise when it is not text."""
    if not isinstance(value, str):
        raise ValueError(f"the task file key {key!r} must be a string")
    return value


def _is_plain_token(value: str) -> bool:
    """True when a value is a plain token: letters, digits, '_' and '-'."""
    return bool(value) and all(char in PART_ID_CHARS for char in value)
