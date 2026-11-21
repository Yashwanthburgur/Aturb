"""Tests for the dated result records.

A run is written to one dated file with one record per task, so a later run
can be compared with it. A record holds exactly the five fields of a result
and nothing else, and the results survive the round trip through the file.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from aturb.evals.report import read_results, write_results
from aturb.evals.result import ERROR, FAILED, OK, TaskResult

FILE_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}\.toml$")


def _results() -> list[TaskResult]:
    """Three results: one ok, one failed and one error."""
    return [
        TaskResult("plate_2holes", "plt0001", OK, 1.0),
        TaskResult(
            "plate_4holes", "plt0002", FAILED, 0.5,
            "the checks did not pass: hole_count"),
        TaskResult(
            "broken_task", "", ERROR, 0.0,
            "the task file could not be read"),
    ]


def _records(path: Path) -> list[dict]:
    """Read the records of a written result file."""
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return raw["results"]


def test_the_written_file_is_named_after_the_run(tmp_path):
    """The file sits in the results folder and carries the date and the time."""
    path = write_results(tmp_path, _results())

    assert path.parent == tmp_path
    assert FILE_NAME.match(path.name)


def test_the_results_folder_is_made_when_it_is_missing(tmp_path):
    """The results folder is created when it is not there."""
    folder = tmp_path / "results"

    path = write_results(folder, _results())

    assert path.parent == folder
    assert path.is_file()


def test_the_file_holds_one_record_per_result(tmp_path):
    """Every result has a record of its own, in the order of the results."""
    results = _results()

    records = _records(write_results(tmp_path, results))

    assert len(records) == len(results)
    assert [record["task_id"] for record in records] == [
        "plate_2holes", "plate_4holes", "broken_task"]


def test_a_record_holds_the_five_fields(tmp_path):
    """A record holds the five fields of a result and nothing else."""
    records = _records(write_results(tmp_path, _results()))

    assert set(records[0]) == {
        "task_id", "part_id", "status", "score", "error"}


def test_an_error_result_keeps_its_task_id_and_its_error_text(tmp_path):
    """An error result keeps its task ID and its error text in the file."""
    records = _records(write_results(tmp_path, _results()))

    record = records[2]
    assert record["task_id"] == "broken_task"
    assert record["status"] == "error"
    assert record["score"] == 0.0
    assert record["error"] == "the task file could not be read"


def test_reading_the_file_back_gives_the_same_results(tmp_path):
    """The results of a run survive the round trip through the file."""
    results = _results()

    path = write_results(tmp_path, results)

    assert read_results(path) == results


def test_a_difficult_error_text_survives_the_round_trip(tmp_path):
    """Quotes, backslashes and newlines in an error text survive the file."""
    text = 'the build failed: "timeout"\\path\nsecond line'
    results = [TaskResult("plate_2holes", "plt0001", ERROR, 0.0, text)]

    path = write_results(tmp_path, results)

    assert read_results(path) == results


def test_a_run_with_no_task_gives_a_file_with_no_record(tmp_path):
    """A run with no task writes a file that holds no record."""
    path = write_results(tmp_path, [])

    assert read_results(path) == []
