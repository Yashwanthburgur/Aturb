"""Tests for the neutral check runner.

The runner calls a list of checks over one model and returns one result per
check, in the same order. A check that raises is reported as a failure, so
one broken check never hides the others.

The models are read from STEP files: the committed plate with two through
holes, and a plate with three holes written on the fly with build123d calls
that are recorded in docs/api_notes/build123d.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from build123d import Box, Cylinder, Location, export_step

from aturb.verify.result import CheckResult
from aturb.verify.runner import hole_count_check, run_checks
from aturb.verify.step import StepLoadError, StepModel, load_step

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "packs" / "stub" / "fixtures" / "plate_2holes.step"


def _passing(name: str):
    """A check that always passes."""

    def check(model: StepModel) -> CheckResult:
        return CheckResult.from_measurement(name, 1.0, 1.0, 0.0)

    check.__name__ = name
    return check


def _failing(name: str):
    """A check that always fails."""

    def check(model: StepModel) -> CheckResult:
        return CheckResult.from_measurement(name, 1.0, 2.0, 0.0)

    check.__name__ = name
    return check


def _raising(name: str):
    """A check that breaks."""

    def check(model: StepModel) -> CheckResult:
        raise RuntimeError(f"{name} broke")

    check.__name__ = name
    return check


def _three_hole_model(tmp_path: Path) -> StepModel:
    """Write a 120 x 60 x 5 plate with three through-holes and read it back."""
    plate = Box(120, 60, 5)
    for x in (-40, 0, 40):
        plate = plate - Cylinder(5, 5).locate(Location((x, 0, 0)))
    path = tmp_path / "plate_3holes.step"
    export_step(plate, str(path))
    return load_step(path)


def test_two_passing_checks_pass():
    """Two passing checks give two passing results."""
    model = load_step(FIXTURE_PATH)

    results = run_checks(model, [_passing("first"), _passing("second")])

    assert len(results) == 2
    assert all(result.passed for result in results)


def test_a_failing_check_is_reported():
    """A check that fails is reported as a failed result."""
    model = load_step(FIXTURE_PATH)

    results = run_checks(model, [_passing("first"), _failing("second")])

    assert results[1].name == "second"
    assert not results[1].passed
    assert results[1].expected == 1.0
    assert results[1].actual == 2.0


def test_a_check_that_raises_is_reported_as_a_failure():
    """A check that breaks is reported as a failure with the exception text."""
    model = load_step(FIXTURE_PATH)

    results = run_checks(model, [_raising("broken")])

    assert len(results) == 1
    assert not results[0].passed
    assert results[0].name == "broken"
    assert results[0].expected is None
    assert results[0].actual is None
    assert "broken broke" in results[0].message


def test_one_broken_check_does_not_hide_the_others():
    """The checks after a broken one still run and still report."""
    model = load_step(FIXTURE_PATH)

    results = run_checks(
        model, [_passing("first"), _raising("broken"), _passing("last")]
    )

    assert [result.name for result in results] == ["first", "broken", "last"]
    assert results[0].passed
    assert not results[1].passed
    assert results[2].passed


def test_the_results_keep_the_order_of_the_checks():
    """The results come back in the order the checks were given in."""
    model = load_step(FIXTURE_PATH)

    results = run_checks(
        model,
        [_passing("one"), _failing("two"), _passing("three"), _raising("four")],
    )

    assert [result.name for result in results] == ["one", "two", "three", "four"]


def test_the_hole_count_check_passes_on_the_fixture():
    """The plate fixture holds two holes, so the check passes."""
    model = load_step(FIXTURE_PATH)

    results = run_checks(model, [hole_count_check(2)])

    assert results[0].passed
    assert results[0].name == "hole_count"
    assert results[0].expected == 2.0
    assert results[0].actual == 2.0


def test_the_hole_count_check_fails_on_a_wrong_count():
    """A wrong expected count fails and reports both numbers."""
    model = load_step(FIXTURE_PATH)

    results = run_checks(model, [hole_count_check(3)])

    assert not results[0].passed
    assert results[0].expected == 3.0
    assert results[0].actual == 2.0


def test_the_hole_count_check_counts_every_hole(tmp_path):
    """A plate with three holes is counted as three."""
    model = _three_hole_model(tmp_path)

    results = run_checks(model, [hole_count_check(3)])

    assert results[0].passed
    assert results[0].actual == 3.0


def test_the_hole_count_check_fails_when_a_hole_is_missing(tmp_path):
    """A plate with three holes fails a check that expects two."""
    model = _three_hole_model(tmp_path)

    results = run_checks(model, [hole_count_check(2)])

    assert not results[0].passed
    assert results[0].expected == 2.0
    assert results[0].actual == 3.0


def test_the_hole_count_check_rejects_a_negative_count():
    """A negative expected count is refused when the check is built."""
    with pytest.raises(ValueError):
        hole_count_check(-1)


def test_the_hole_count_check_rejects_a_count_that_is_not_a_number():
    """An expected count that is not an integer is refused."""
    with pytest.raises(TypeError):
        hole_count_check("two")


def test_a_missing_step_file_stops_the_run(tmp_path):
    """A STEP file that cannot be read stops the run before any check."""
    with pytest.raises(StepLoadError):
        load_step(tmp_path / "absent.step")


def test_a_check_that_cannot_read_its_file_is_reported_as_a_failure(tmp_path):
    """A check that raises on a missing file is reported as a failure."""
    model = load_step(FIXTURE_PATH)
    missing = tmp_path / "absent.step"

    def check(model: StepModel) -> CheckResult:
        load_step(missing)
        return CheckResult.from_measurement("never", 1.0, 1.0, 0.0)

    check.__name__ = "reads_a_missing_file"

    results = run_checks(model, [check])

    assert len(results) == 1
    assert not results[0].passed
    assert results[0].name == "reads_a_missing_file"
    assert "absent.step" in results[0].message


def test_a_check_that_cannot_read_a_broken_file_is_reported_as_a_failure(tmp_path):
    """A check that raises on a broken file is reported as a failure.

    The STEP reader also writes a parse error to stderr for this file. That
    message comes from the reader itself, so Python cannot capture it.
    """
    model = load_step(FIXTURE_PATH)
    broken = tmp_path / "broken.step"
    broken.write_text("this is not a STEP file", encoding="utf-8")

    def check(model: StepModel) -> CheckResult:
        load_step(broken)
        return CheckResult.from_measurement("never", 1.0, 1.0, 0.0)

    check.__name__ = "reads_a_broken_file"

    results = run_checks(model, [check])

    assert len(results) == 1
    assert not results[0].passed
    assert results[0].name == "reads_a_broken_file"
    assert "broken.step" in results[0].message
