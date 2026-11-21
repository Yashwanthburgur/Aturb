"""Tests for the task result type.

A task has three outcomes: ok, failed and error. The type carries the outcome
and the score; the rule that turns check results into a score belongs to the
scoring layer, so the result type never computes one.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from aturb.evals.result import (
    ERROR,
    FAILED,
    OK,
    TaskResult,
    passed_count,
    set_score,
)


def test_the_three_statuses_are_accepted():
    """An ok, a failed and an error result are all allowed."""
    ok = TaskResult("plate_2holes", "plt0001", OK, 1.0)
    failed = TaskResult(
        "plate_2holes", "plt0001", FAILED, 0.5, "the checks did not pass")
    error = TaskResult("plate_2holes", "", ERROR, 0.0, "the build failed")

    assert ok.status == "ok"
    assert failed.status == "failed"
    assert error.status == "error"


def test_another_status_raises():
    """A status the model does not know is refused."""
    with pytest.raises(ValueError):
        TaskResult("plate_2holes", "plt0001", "unknown", 1.0)


def test_to_dict_returns_the_five_fields():
    """The dict holds the five fields of the result."""
    result = TaskResult("plate_2holes", "plt0001", OK, 1.0)

    assert result.to_dict() == {
        "task_id": "plate_2holes",
        "part_id": "plt0001",
        "status": "ok",
        "score": 1.0,
        "error": "",
    }


def test_the_result_is_json_serializable():
    """The dict of a result can be stored as JSON."""
    result = TaskResult(
        "plate_2holes", "plt0001", FAILED, 0.5, "the checks did not pass")

    loaded = json.loads(json.dumps(result.to_dict()))

    assert loaded["status"] == "failed"
    assert loaded["score"] == 0.5


def test_the_result_is_frozen():
    """A result cannot be changed once it is made."""
    result = TaskResult("plate_2holes", "plt0001", OK, 1.0)

    with pytest.raises(FrozenInstanceError):
        result.score = 0.5


def test_a_negative_score_raises():
    """A score below 0.0 is refused."""
    with pytest.raises(ValueError):
        TaskResult("plate_2holes", "plt0001", FAILED, -
                   0.5, "the checks did not pass")


def test_a_score_above_one_is_allowed():
    """The ceiling of a score is the max_score of its task, not 1.0."""
    result = TaskResult("plate_2holes", "plt0001", OK, 2.0)

    assert result.score == 2.0


def test_an_ok_task_must_not_carry_an_error_text():
    """A task that passed has nothing to report."""
    with pytest.raises(ValueError):
        TaskResult("plate_2holes", "plt0001", OK,
                   1.0, "the checks did not pass")


def test_a_build_failure_is_an_error():
    """A build failure is an error result that keeps its text."""
    result = TaskResult.from_error(
        "plate_2holes", "plt0001", "the build failed: timeout")

    assert result.status == ERROR
    assert result.score == 0.0
    assert result.error == "the build failed: timeout"


def test_a_build_failure_stays_distinct_from_a_geometry_failure():
    """A build failure and a failed check are two different outcomes."""
    build_failure = TaskResult.from_error(
        "plate_2holes", "plt0001", "the build failed")
    geometry_failure = TaskResult(
        "plate_2holes", "plt0001", FAILED, 0.5, "the checks did not pass: volume")

    assert build_failure.status == ERROR
    assert geometry_failure.status == FAILED
    assert build_failure.status != geometry_failure.status


def test_set_score_is_the_mean_task_score():
    """The score of a task set is the mean score of its tasks."""
    results = [
        TaskResult("a", "p1", OK, 1.0),
        TaskResult("b", "p2", FAILED, 0.5),
        TaskResult("c", "", ERROR, 0.0),
    ]

    assert set_score(results) == pytest.approx(0.5)


def test_set_score_of_an_empty_set_is_zero():
    """A task set with no tasks has a score of 0.0."""
    assert set_score([]) == 0.0


def test_passed_count_counts_the_passed_tasks():
    """Only the tasks that passed are counted."""
    results = [
        TaskResult("a", "p1", OK, 1.0),
        TaskResult("b", "p2", FAILED, 0.5),
        TaskResult("c", "", ERROR, 0.0),
        TaskResult("d", "p4", OK, 1.0),
    ]

    assert passed_count(results) == 2
