"""Tests for the batch runner.

A task set is a folder of task folders, and the batch holds exactly one
result per folder. A malformed task is a result of its own: it is never
skipped, it never stops the batch and it never hides a good task.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from aturb.evals.batch import run_batch
from aturb.evals.result import ERROR, OK
from aturb.packs import default_packs_root, load_runner

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "evals" / "tasks" / "plate_2holes"


def make_runner():
    """Load the stub runner with empty settings."""
    return load_runner("stub", {"packs": {}}, default_packs_root())


def copy_task(tmp_path: Path, name: str) -> Path:
    """Copy the committed task into a tmp folder under the given name.

    The task ID of a task is the name of its folder, so the task file and the
    answer file are renamed with the folder.
    """
    folder = tmp_path / name
    shutil.copytree(TASK_DIR, folder, ignore=shutil.ignore_patterns("out"))
    for file_name in ("task.toml", "answer.toml"):
        path = folder / file_name
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                'task_id = "plate_2holes"', f'task_id = "{name}"'),
            encoding="utf-8")
    return folder


def test_two_good_tasks_give_two_results_in_sorted_order(tmp_path):
    """A set of two good tasks gives two results, in folder name order."""
    copy_task(tmp_path, "plate_b")
    copy_task(tmp_path, "plate_a")

    results = run_batch(tmp_path, make_runner(), 60)

    assert [result.task_id for result in results] == ["plate_a", "plate_b"]
    assert all(result.status == OK for result in results)
    assert all(result.score == 1.0 for result in results)


def test_a_task_without_a_task_file_is_an_error_result(tmp_path):
    """A folder without a task file is an error result named after the folder."""
    (tmp_path / "no_task_file").mkdir()

    results = run_batch(tmp_path, make_runner(), 60)

    assert len(results) == 1
    assert results[0].status == ERROR
    assert results[0].task_id == "no_task_file"
    assert results[0].part_id == ""
    assert results[0].score == 0.0


def test_a_task_with_an_invalid_task_file_is_an_error_result(tmp_path):
    """A folder with an invalid task file is an error result named after it."""
    folder = tmp_path / "bad_task_file"
    folder.mkdir()
    (folder / "task.toml").write_text('task_id = "other"\n', encoding="utf-8")

    results = run_batch(tmp_path, make_runner(), 60)

    assert len(results) == 1
    assert results[0].status == ERROR
    assert results[0].task_id == "bad_task_file"
    assert results[0].part_id == ""


def test_a_good_task_is_still_scored_in_a_malformed_batch(tmp_path):
    """A malformed task never stops the batch and never hides a good task."""
    copy_task(tmp_path, "plate_good")
    (tmp_path / "no_task_file").mkdir()
    broken = tmp_path / "bad_task_file"
    broken.mkdir()
    (broken / "task.toml").write_text("task_id = 'x\n", encoding="utf-8")

    results = run_batch(tmp_path, make_runner(), 60)

    assert [result.task_id for result in results] == [
        "bad_task_file", "no_task_file", "plate_good"]
    assert results[0].status == ERROR
    assert results[1].status == ERROR
    assert results[2].status == OK
    assert results[2].score == 1.0


def test_the_batch_holds_one_result_per_folder(tmp_path):
    """The list holds exactly one result per task folder."""
    copy_task(tmp_path, "plate_a")
    copy_task(tmp_path, "plate_b")
    (tmp_path / "broken").mkdir()

    results = run_batch(tmp_path, make_runner(), 60)

    assert len(results) == 3
    assert len({result.task_id for result in results}) == 3


def test_a_file_in_the_tasks_root_is_not_a_task(tmp_path):
    """Only the folders of the tasks root are tasks."""
    (tmp_path / "notes.txt").write_text("not a task", encoding="utf-8")
    copy_task(tmp_path, "plate_a")

    results = run_batch(tmp_path, make_runner(), 60)

    assert [result.task_id for result in results] == ["plate_a"]
