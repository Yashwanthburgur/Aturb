"""Tests for the judgement of one task.

The judgement holds the result of the task and the candidate-only geometry
summary: what the candidate itself measures, with no evaluator field in it.
"""

from __future__ import annotations

import shutil
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from aturb.contract.types import BuildRequest, BuildResult, FailureKind, PackInfo
from aturb.evals.judge import (
    CandidateGeometry,
    HoleSummary,
    TaskJudgement,
    judge_task,
    sanitize_text,
    summarize_geometry,
)
from aturb.evals.result import ERROR, FAILED, OK
from aturb.packs import default_packs_root, load_runner
from aturb.verify.holes import find_holes
from aturb.verify.step import load_step

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "evals" / "tasks" / "plate_2holes"

FORBIDDEN_FIELDS = (
    "expected",
    "tolerance",
    "passed",
    "message",
    "check_name",
    "CheckResult",
    "AnswerSpec",
    "failed_check_names",
)

WRONG_VOLUME = """\
volume = 999.0
bbox = [120.0, 60.0, 5.0]
hole_count = 2
hole_diameter = 10.0
hole_positions = [[-40.0, 0.0], [40.0, 0.0]]
"""


def make_runner():
    """Load the stub runner with empty settings."""
    return load_runner("stub", {"packs": {}}, default_packs_root())


def copy_task(tmp_path: Path) -> Path:
    """Copy the committed task into a tmp folder and return it."""
    folder = tmp_path / "plate_2holes"
    shutil.copytree(TASK_DIR, folder, ignore=shutil.ignore_patterns("out"))
    return folder


class FakeRunner:
    """A runner that reports a chosen build result."""

    def __init__(self, build: BuildResult):
        self.build_result = build

    def info(self) -> PackInfo:
        """Describe the pack."""
        return PackInfo(name="stub", language="stub-text", version="0.1")

    def build(self, request: BuildRequest) -> BuildResult:
        """Report the chosen build result."""
        return self.build_result


def test_the_candidate_summary_holds_no_evaluator_field():
    """The summary holds the measured fields and no evaluator field."""
    names = {field.name for field in fields(CandidateGeometry)}

    assert names == {
        "is_valid", "is_single_solid", "volume", "bbox_size", "holes"}
    for forbidden in FORBIDDEN_FIELDS:
        assert forbidden not in names


def test_the_judgement_holds_no_evaluator_field():
    """The judgement holds the result and the candidate side, and nothing else."""
    names = {field.name for field in fields(TaskJudgement)}

    assert names == {
        "result", "geometry", "build_status", "failure_kind",
        "error_text", "diagnostics"}
    for forbidden in FORBIDDEN_FIELDS:
        assert forbidden not in names


def test_no_evaluator_type_is_named_by_a_field():
    """No field of the judgement names an evaluator type."""
    for field in fields(TaskJudgement):
        assert "CheckResult" not in str(field.type)
        assert "AnswerSpec" not in str(field.type)
    for field in fields(CandidateGeometry):
        assert "CheckResult" not in str(field.type)
        assert "AnswerSpec" not in str(field.type)


def test_a_successful_build_measures_the_candidate(tmp_path):
    """A build that succeeded measures the candidate from its own STEP file."""
    folder = copy_task(tmp_path)

    judgement = judge_task(folder, make_runner(), 60)

    assert judgement.result.status == OK
    assert judgement.build_status == "ok"
    assert judgement.failure_kind == ""
    assert judgement.error_text == ""
    assert judgement.diagnostics == ()
    geometry = judgement.geometry
    assert geometry is not None
    assert geometry.is_valid is True
    assert geometry.is_single_solid is True
    assert geometry.volume == pytest.approx(35214.602, abs=0.01)
    assert geometry.bbox_size == pytest.approx((120.0, 60.0, 5.0))
    assert [value for hole in geometry.holes
            for value in (hole.diameter, hole.x, hole.y)] == pytest.approx(
        [10.0, -40.0, 0.0, 10.0, 40.0, 0.0])


def test_the_summary_is_measured_from_the_model(tmp_path):
    """The summary is measured from the model, with the neutral readers."""
    folder = copy_task(tmp_path)
    judge_task(folder, make_runner(), 60)
    model = load_step(folder / "project" / "out" / "plt0001" / "plt0001.step")

    geometry = summarize_geometry(model)

    assert geometry.is_valid == model.is_valid
    assert geometry.is_single_solid == model.is_single_solid
    assert geometry.volume == pytest.approx(model.volume)
    assert geometry.bbox_size == pytest.approx(
        (model.bbox_size.X, model.bbox_size.Y, model.bbox_size.Z))
    assert geometry.holes == tuple(
        HoleSummary(diameter=hole.diameter, x=hole.x, y=hole.y)
        for hole in find_holes(model))


def test_a_failed_build_has_no_geometry(tmp_path):
    """A build that failed has no geometry and says how it failed."""
    folder = copy_task(tmp_path)
    (folder / "project" / "parts" / "plt0001_base_plate.stub").write_text(
        "# STUB: fail=runtime_error\n", encoding="utf-8")

    judgement = judge_task(folder, make_runner(), 60)

    assert judgement.result.status == ERROR
    assert judgement.geometry is None
    assert judgement.build_status == "failed"
    assert judgement.failure_kind == "runtime_error"
    assert judgement.error_text == "scripted failure: runtime_error"


def test_a_step_file_that_cannot_be_read_has_no_geometry():
    """A STEP file that is not there leaves the judgement without geometry."""
    runner = FakeRunner(BuildResult(
        status="ok", artifacts={"step": "out/plt0001/gone.step"}))

    judgement = judge_task(TASK_DIR, runner, 60)

    assert judgement.result.status == ERROR
    assert judgement.geometry is None
    assert judgement.build_status == "ok"
    assert judgement.failure_kind == ""


def test_the_build_outcome_is_reported():
    """The status, the failure kind, the error text and the diagnostics of the
    judgement come from the build result."""
    runner = FakeRunner(BuildResult(
        status="failed",
        failure_kind=FailureKind.RUNTIME_ERROR,
        error_text="boom in C:\\Users\\Yashwanth\\file.py",
        native_diagnostics={"note": "see /home/user/file.py"},
    ))

    judgement = judge_task(TASK_DIR, runner, 60)

    assert judgement.build_status == "failed"
    assert judgement.failure_kind == "runtime_error"
    assert judgement.error_text == "boom in file.py"
    assert judgement.diagnostics == ("note: see file.py",)
    assert judgement.result.status == ERROR
    assert judgement.result.error == "boom in C:\\Users\\Yashwanth\\file.py"


def test_the_sanitizer_removes_a_windows_path():
    """A Windows path loses its drive letter and its directories."""
    text = 'File "C:\\Users\\Yashwanth\\OneDrive\\file.py", line 12, in <module>'

    assert sanitize_text(text) == 'File "file.py", line 12, in <module>'


def test_the_sanitizer_removes_a_posix_path():
    """A POSIX path loses its directories."""
    text = 'File "/home/user/project/file.py", line 3, in <module>'

    assert sanitize_text(text) == 'File "file.py", line 3, in <module>'


def test_the_sanitizer_keeps_the_message():
    """A message without a path is left alone."""
    text = "SyntaxError: invalid syntax"

    assert sanitize_text(text) == text


def test_the_result_is_the_frozen_five_field_result():
    """The result of the judgement is the frozen five-field result."""
    judgement = judge_task(TASK_DIR, make_runner(), 60)
    result = judgement.result

    assert [field.name for field in fields(result)] == [
        "task_id", "part_id", "status", "score", "error"]
    name = "score"
    with pytest.raises(FrozenInstanceError):
        setattr(result, name, 0.0)


def test_the_score_still_comes_from_the_scoring_rule(tmp_path):
    """The score of a task whose checks did not pass is the Phase 4 score."""
    folder = copy_task(tmp_path)
    (folder / "project" / "expect" / "plt0001.toml").write_text(
        WRONG_VOLUME, encoding="utf-8")

    judgement = judge_task(folder, make_runner(), 60)

    assert judgement.result.status == FAILED
    assert judgement.result.score == 0.8
    assert judgement.result.error == "the checks did not pass: volume"


def test_the_summary_does_not_come_from_the_expectation_file(tmp_path):
    """The summary is what the candidate measures, whatever the target is."""
    folder = copy_task(tmp_path)
    (folder / "project" / "expect" / "plt0001.toml").write_text(
        WRONG_VOLUME, encoding="utf-8")

    judgement = judge_task(folder, make_runner(), 60)

    geometry = judgement.geometry
    assert geometry is not None
    assert geometry.volume == pytest.approx(35214.602, abs=0.01)
    assert geometry.bbox_size == pytest.approx((120.0, 60.0, 5.0))
    assert len(geometry.holes) == 2


@pytest.mark.parametrize("broken", ["missing", "invalid"])
def test_the_summary_survives_a_broken_expectation_file(tmp_path, broken):
    """A broken expectation file is an error, and the summary is still there."""
    folder = copy_task(tmp_path)
    expect = folder / "project" / "expect" / "plt0001.toml"
    if broken == "missing":
        expect.unlink()
    else:
        expect.write_text("volume = [not toml\n", encoding="utf-8")

    judgement = judge_task(folder, make_runner(), 60)

    assert judgement.result.status == ERROR
    assert "expectation file" in judgement.result.error
    geometry = judgement.geometry
    assert geometry is not None
    assert geometry.is_valid is True
    assert geometry.is_single_solid is True
    assert geometry.volume == pytest.approx(35214.602, abs=0.01)
    assert geometry.bbox_size == pytest.approx((120.0, 60.0, 5.0))
    assert len(geometry.holes) == 2
