"""Tests for the scoring rule of a task.

The score of a task is the fraction of its required checks that passed,
scaled by the score a fully correct answer earns. Only the checks named in
the answer count, and a required check that the results do not hold counts as
failed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aturb.evals.answer import AnswerSpec, load_answer
from aturb.evals.result import FAILED, OK
from aturb.evals.scoring import score_task, task_status
from aturb.verify.result import CheckResult

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "evals" / "tasks" / "plate_2holes"


def _answer(
    required_checks: tuple[str, ...] = ("volume", "bbox_x"),
    max_score: float = 1.0,
) -> AnswerSpec:
    """An answer that requires the given checks."""
    return AnswerSpec(
        task_id="plate_2holes",
        part_id="plt0001",
        expect_file="expect/plt0001.toml",
        required_checks=required_checks,
        max_score=max_score,
    )


def _passing(name: str) -> CheckResult:
    """A check that passed."""
    return CheckResult.from_measurement(name, 1.0, 1.0, 0.01)


def _failing(name: str) -> CheckResult:
    """A check that failed."""
    return CheckResult.from_measurement(name, 1.0, 2.0, 0.01)


def test_the_committed_answer_names_its_required_checks():
    """The committed answer requires the five checks of the roadmap."""
    answer = load_answer(TASK_DIR)

    assert answer.required_checks == (
        "volume", "bbox_x", "bbox_y", "bbox_z", "hole_count")
    assert answer.max_score == 1.0


def test_every_required_check_passing_gives_the_full_score():
    """A task whose required checks all pass earns the full score."""
    answer = load_answer(TASK_DIR)
    checks = [_passing(name) for name in answer.required_checks]

    score, error_text = score_task(answer, checks)

    assert score == answer.max_score
    assert error_text == ""


def test_one_failing_check_lowers_the_score_in_proportion():
    """One failing check of four lowers the score to three quarters."""
    answer = _answer(("volume", "bbox_x", "bbox_y", "bbox_z"))
    checks = [
        _passing("volume"),
        _passing("bbox_x"),
        _passing("bbox_y"),
        _failing("bbox_z"),
    ]

    score, error_text = score_task(answer, checks)

    assert score == pytest.approx(0.75)
    assert "bbox_z" in error_text


def test_a_missing_required_check_counts_as_failed():
    """A required check the results do not hold counts as failed."""
    answer = _answer(("volume", "bbox_x"))
    checks = [_passing("volume")]

    score, error_text = score_task(answer, checks)

    assert score == pytest.approx(0.5)
    assert "bbox_x" in error_text


def test_a_check_that_is_not_required_is_ignored():
    """A failing check the answer does not require does not lower the score."""
    answer = _answer(("volume",))
    checks = [_passing("volume"), _failing("bbox_x")]

    score, error_text = score_task(answer, checks)

    assert score == 1.0
    assert error_text == ""


def test_the_error_text_names_the_checks_that_did_not_pass():
    """The error text names every check that did not pass."""
    answer = _answer(("volume", "bbox_x", "bbox_y"))
    checks = [_passing("volume"), _failing("bbox_x"), _failing("bbox_y")]

    _, error_text = score_task(answer, checks)

    assert "bbox_x" in error_text
    assert "bbox_y" in error_text
    assert "volume" not in error_text


def test_the_score_is_scaled_by_the_max_score():
    """The score of a task is scaled by the score of a full answer."""
    answer = _answer(("volume", "bbox_x"), max_score=2.0)
    checks = [_passing("volume"), _failing("bbox_x")]

    score, _ = score_task(answer, checks)

    assert score == pytest.approx(1.0)


def test_a_task_is_ok_when_every_required_check_passes():
    """A task whose required checks all pass is ok."""
    answer = _answer(("volume", "bbox_x"))
    checks = [_passing("volume"), _passing("bbox_x")]

    assert task_status(answer, checks) == OK


def test_a_task_is_failed_when_a_required_check_fails():
    """A task with a failing required check is failed."""
    answer = _answer(("volume", "bbox_x"))
    checks = [_passing("volume"), _failing("bbox_x")]

    assert task_status(answer, checks) == FAILED


def test_a_task_with_a_missing_required_check_is_failed():
    """A task whose required check is missing from the results is failed."""
    answer = _answer(("volume", "bbox_x"))
    checks = [_passing("volume")]

    assert task_status(answer, checks) == FAILED


def test_an_answer_with_no_required_check_cannot_be_scored():
    """An answer that requires no check has nothing to score."""
    answer = _answer(())

    with pytest.raises(ValueError):
        score_task(answer, [_passing("volume")])
