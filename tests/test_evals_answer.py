"""Tests for the answer file loader.

The committed answer of the first task holds the five keys of the answer
schema. The loader must accept exactly those five keys, must keep the answer
tied to the task of the folder, and must refuse an expectation file that
leaves the expect folder of the task project.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aturb.evals.answer import AnswerSpec, load_answer
from aturb.verify.expectations import checks_from_expectations, load_expectations
from aturb.verify.step import load_step

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "evals" / "tasks" / "plate_2holes"
EXPECT_PATH = TASK_DIR / "project" / "expect" / "plt0001.toml"
FIXTURE_PATH = REPO_ROOT / "packs" / "stub" / "fixtures" / "plate_2holes.step"

TASK_FILE = """\
task_id = "plate_2holes"
part_id = "plt0001"
name = "Plate with two through holes"
description = "Build a 120 x 60 x 5 mm plate with two 10 mm through holes."
"""

ANSWER_FILE = """\
task_id = "plate_2holes"
part_id = "plt0001"
expect_file = "expect/plt0001.toml"
required_checks = ["volume", "bbox_x", "bbox_y", "bbox_z", "hole_count"]
max_score = 1.0
"""

CHECKS_LINE = 'required_checks = ["volume", "bbox_x", "bbox_y", "bbox_z", "hole_count"]'


def _task_folder(tmp_path: Path, answer_text: str) -> Path:
    """Write a task file and an answer file into a task folder."""
    folder = tmp_path / "plate_2holes"
    folder.mkdir()
    (folder / "task.toml").write_text(TASK_FILE, encoding="utf-8")
    (folder / "answer.toml").write_text(answer_text, encoding="utf-8")
    return folder


def test_the_committed_answer_loads():
    """The committed answer loads into the five fields of the schema."""
    spec = load_answer(TASK_DIR)

    assert isinstance(spec, AnswerSpec)
    assert spec.task_id == "plate_2holes"
    assert spec.part_id == "plt0001"
    assert spec.expect_file == "expect/plt0001.toml"
    assert spec.required_checks == (
        "volume", "bbox_x", "bbox_y", "bbox_z", "hole_count")
    assert spec.max_score == 1.0


def test_an_answer_with_six_keys_raises(tmp_path):
    """A file with a sixth key is refused."""
    folder = _task_folder(tmp_path, ANSWER_FILE +
                          'prompt = "Build the plate."\n')

    with pytest.raises(ValueError):
        load_answer(folder)


def test_an_answer_with_four_keys_raises(tmp_path):
    """A file without every key is refused."""
    folder = _task_folder(
        tmp_path, ANSWER_FILE.replace("max_score = 1.0\n", ""))

    with pytest.raises(ValueError):
        load_answer(folder)


def test_an_absolute_expect_file_raises(tmp_path):
    """An expectation file outside the task project is refused."""
    absolute = (tmp_path / "elsewhere.toml").as_posix()
    folder = _task_folder(
        tmp_path,
        ANSWER_FILE.replace(
            'expect_file = "expect/plt0001.toml"',
            f'expect_file = "{absolute}"'),
    )

    with pytest.raises(ValueError):
        load_answer(folder)


def test_an_empty_required_checks_raises(tmp_path):
    """An answer that requires no check at all is refused."""
    folder = _task_folder(
        tmp_path,
        ANSWER_FILE.replace(CHECKS_LINE, "required_checks = []"),
    )

    with pytest.raises(ValueError):
        load_answer(folder)


def test_an_answer_for_another_task_raises(tmp_path):
    """An answer that names another task is refused."""
    folder = _task_folder(
        tmp_path,
        ANSWER_FILE.replace('task_id = "plate_2holes"',
                            'task_id = "other_task"'),
    )

    with pytest.raises(ValueError):
        load_answer(folder)


def test_an_answer_for_another_part_raises(tmp_path):
    """An answer that names another part is refused."""
    folder = _task_folder(
        tmp_path,
        ANSWER_FILE.replace('part_id = "plt0001"', 'part_id = "plt0002"'),
    )

    with pytest.raises(ValueError):
        load_answer(folder)


def test_an_expect_file_outside_the_expect_folder_raises(tmp_path):
    """An expectation file that leaves the expect folder is refused."""
    folder = _task_folder(
        tmp_path,
        ANSWER_FILE.replace(
            'expect_file = "expect/plt0001.toml"',
            'expect_file = "../outside.toml"'),
    )

    with pytest.raises(ValueError):
        load_answer(folder)


def test_an_unknown_check_name_raises(tmp_path):
    """A check name the verification layer does not produce is refused."""
    folder = _task_folder(
        tmp_path,
        ANSWER_FILE.replace(
            CHECKS_LINE, 'required_checks = ["volume", "mass"]'),
    )

    with pytest.raises(ValueError):
        load_answer(folder)


def test_the_check_names_of_the_implementation_are_accepted(tmp_path):
    """Every name checks_from_expectations() produces is a valid check name."""
    model = load_step(FIXTURE_PATH)
    expected = load_expectations(EXPECT_PATH)
    names = [result.name for result in checks_from_expectations(
        model, expected)]

    folder = _task_folder(
        tmp_path,
        ANSWER_FILE.replace(CHECKS_LINE, f"required_checks = {names!r}"),
    )

    spec = load_answer(folder)

    assert list(spec.required_checks) == names
