"""Read the answer file of one task folder and refuse a file that cannot be trusted.

The answer file holds the correct answer of a task: the identity of the task
and of the part it builds, the expectation file that holds the expected values,
the checks that must pass and the score a fully correct answer earns.

The schema is exactly five keys and does not grow in Phase 4. The answer file
stays outside the candidate project, so the candidate never reads it.

The answer belongs to the task of the folder, so the loader reads the task file
first and checks that the two agree on the task ID and on the part ID.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from aturb.evals.task import TaskSpec, load_task
from aturb.workspace.paths import PathEscapeError, resolve_inside

ANSWER_FILE_NAME = "answer.toml"

REQUIRED_KEYS = ("task_id", "part_id", "expect_file",
                 "required_checks", "max_score")

PROJECT_DIR_NAME = "project"
EXPECT_DIR_NAME = "expect"

# The names checks_from_expectations() produces: the five base checks, and the
# per-hole checks, which carry the index of the hole.
BASE_CHECKS = frozenset({"volume", "bbox_x", "bbox_y", "bbox_z", "hole_count"})
HOLE_CHECK = re.compile(r"hole_\d+_(?:diameter|x|y)")


@dataclass(frozen=True)
class AnswerSpec:
    """What the answer file of one task says.

    ``required_checks`` holds the names of the checks that must pass, in the
    order the answer file lists them.
    """

    task_id: str
    part_id: str
    expect_file: str
    required_checks: tuple[str, ...]
    max_score: float


def load_answer(task_dir: Path) -> AnswerSpec:
    """Load the answer file of one task folder.

    The answer file is ``<task_dir>/answer.toml``. It accepts exactly the five
    keys of the answer schema: a missing key or an unknown key raises
    ``ValueError``. The answer must belong to the task of the folder, its
    ``expect_file`` must be a relative path inside the ``expect/`` folder of
    the task project, ``required_checks`` must be a non-empty list of check
    names and ``max_score`` must be a positive number.
    """
    task_dir = Path(task_dir)
    task = load_task(task_dir)
    path = _answer_file(task_dir)
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc
    return _spec(raw, task, task_dir, path)


def _answer_file(task_dir: Path) -> Path:
    """Return the answer file of a task folder, resolved inside that folder."""
    try:
        return resolve_inside(task_dir, ANSWER_FILE_NAME)
    except PathEscapeError as exc:
        raise ValueError(
            f"the answer file is outside the task folder: {exc}") from exc


def _spec(raw: dict, task: TaskSpec, task_dir: Path, path: Path) -> AnswerSpec:
    """Check the answer file and return the answer it describes."""
    missing = [key for key in REQUIRED_KEYS if key not in raw]
    if missing:
        raise ValueError(
            f"answer file {path} is missing key(s): {', '.join(missing)}")
    unknown = sorted(set(raw) - set(REQUIRED_KEYS))
    if unknown:
        raise ValueError(
            f"answer file {path} has unknown key(s): {', '.join(unknown)}")

    task_id = _text(raw["task_id"], "task_id")
    part_id = _text(raw["part_id"], "part_id")
    if task_id != task.task_id:
        raise ValueError(
            f"the answer names task {task_id!r}, but the task folder holds "
            f"task {task.task_id!r}")
    if part_id != task.part_id:
        raise ValueError(
            f"the answer names part {part_id!r}, but the task builds part "
            f"{task.part_id!r}")

    expect_file = _text(raw["expect_file"], "expect_file")
    _check_expect_file(expect_file, task_dir)
    return AnswerSpec(
        task_id=task_id,
        part_id=part_id,
        expect_file=expect_file,
        required_checks=_checks(raw["required_checks"]),
        max_score=_positive_number(raw["max_score"], "max_score"),
    )


def _check_expect_file(expect_file: str, task_dir: Path) -> None:
    """Check that the expectation file is a relative path inside expect/.

    The path is relative to the build project of the task, and it must land in
    the ``expect/`` folder of that project.
    """
    if Path(expect_file).is_absolute():
        raise ValueError(
            f"expect_file {expect_file!r} must be a relative path")
    project = task_dir / PROJECT_DIR_NAME
    try:
        resolved = resolve_inside(project, expect_file)
    except PathEscapeError as exc:
        raise ValueError(
            f"expect_file {expect_file!r} is outside the task project: "
            f"{exc}") from exc
    expect_dir = (project / EXPECT_DIR_NAME).resolve()
    if not resolved.is_relative_to(expect_dir):
        raise ValueError(
            f"expect_file {expect_file!r} is outside the expect folder of the "
            f"task project")


def _checks(value) -> tuple[str, ...]:
    """Return the required check names, or raise when they are not names."""
    if not isinstance(value, list) or not value:
        raise ValueError("required_checks must be a non-empty list of names")
    names = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("required_checks must hold names only")
        if not _is_check_name(item):
            raise ValueError(f"unknown check name {item!r}")
        names.append(item)
    return tuple(names)


def _is_check_name(name: str) -> bool:
    """True when a name is one of the checks checks_from_expectations() gives."""
    return name in BASE_CHECKS or HOLE_CHECK.fullmatch(name) is not None


def _text(value, key: str) -> str:
    """Return a value as text, or raise when it is not text."""
    if not isinstance(value, str):
        raise ValueError(f"the answer file key {key!r} must be a string")
    return value


def _positive_number(value, key: str) -> float:
    """Return a value as a positive number, or raise when it is not one."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"the answer file key {key!r} must be a number")
    number = float(value)
    if number <= 0:
        raise ValueError(f"the answer file key {key!r} must be positive")
    return number
