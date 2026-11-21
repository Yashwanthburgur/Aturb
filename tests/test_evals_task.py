"""Tests for the task file loader.

The committed task of the set is the proof that a task ID and a part ID are
two different things: the task is plate_2holes and the part it builds is
plt0001. The loader must keep them apart and must never guess one from the
other.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aturb.evals.task import TaskSpec, load_task

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "evals" / "tasks" / "plate_2holes"

VALID_TASK = """\
task_id = "plate_2holes"
part_id = "plt0001"
name = "Plate with two through holes"
description = "Build a 120 x 60 x 5 mm plate with two 10 mm through holes."
"""


def _task_folder(tmp_path: Path, text: str) -> Path:
    """Write a task file into a task folder and return the folder."""
    folder = tmp_path / "plate_2holes"
    folder.mkdir()
    (folder / "task.toml").write_text(text, encoding="utf-8")
    return folder


def test_the_committed_task_loads():
    """The committed task loads, and its task ID and part ID stay apart."""
    spec = load_task(TASK_DIR)

    assert isinstance(spec, TaskSpec)
    assert spec.task_id == "plate_2holes"
    assert spec.part_id == "plt0001"
    assert spec.name == "Plate with two through holes"
    assert spec.description
    assert spec.task_id != spec.part_id


def test_a_valid_task_loads(tmp_path):
    """A task file with the four keys loads into a task spec."""
    folder = _task_folder(tmp_path, VALID_TASK)

    spec = load_task(folder)

    assert spec == TaskSpec(
        task_id="plate_2holes",
        part_id="plt0001",
        name="Plate with two through holes",
        description="Build a 120 x 60 x 5 mm plate with two 10 mm through holes.",
    )


def test_a_missing_task_file_raises(tmp_path):
    """A task folder without a task file cannot be loaded."""
    folder = tmp_path / "plate_2holes"
    folder.mkdir()

    with pytest.raises(FileNotFoundError):
        load_task(folder)


def test_malformed_toml_raises(tmp_path):
    """A task file that is not valid TOML is refused."""
    folder = _task_folder(tmp_path, 'task_id = "plate_2holes\n')

    with pytest.raises(ValueError):
        load_task(folder)


def test_a_missing_key_raises(tmp_path):
    """A task file without every key is refused."""
    folder = _task_folder(
        tmp_path,
        'task_id = "plate_2holes"\n'
        'name = "Plate with two through holes"\n'
        'description = "Build a plate with two through holes."\n',
    )

    with pytest.raises(ValueError):
        load_task(folder)


def test_an_unknown_key_raises(tmp_path):
    """A task file with a key the schema does not know is refused."""
    folder = _task_folder(
        tmp_path,
        VALID_TASK + 'expect_file = "expect/plt0001.toml"\n',
    )

    with pytest.raises(ValueError):
        load_task(folder)


def test_a_task_id_that_differs_from_the_folder_raises(tmp_path):
    """A task file whose task ID is not the folder name is refused."""
    folder = _task_folder(
        tmp_path,
        VALID_TASK.replace('task_id = "plate_2holes"',
                           'task_id = "other_task"'),
    )

    with pytest.raises(ValueError):
        load_task(folder)


def test_a_part_id_with_a_path_separator_raises(tmp_path):
    """A part ID that is a path is refused."""
    folder = _task_folder(
        tmp_path,
        VALID_TASK.replace('part_id = "plt0001"', 'part_id = "parts/plt0001"'),
    )

    with pytest.raises(ValueError):
        load_task(folder)
