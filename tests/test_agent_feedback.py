"""Tests for the repair feedback block.

The block tells the agent what its own candidate did. It never carries an
evaluator-derived field, and the formatter has no parameter that could carry
one.
"""

from __future__ import annotations

import inspect
from dataclasses import fields
from typing import Any

import pytest

from aturb.agent.feedback import BuildFeedback, feedback_text
from aturb.evals.judge import CandidateGeometry, HoleSummary

FORBIDDEN_FIELDS = (
    "passed",
    "score",
    "expected",
    "tolerance",
    "check_name",
    "TaskResult",
    "TaskJudgement",
    "CheckResult",
    "AnswerSpec",
    "expect_path",
    "expect_file",
)

FORBIDDEN_KEYWORDS = (
    "expected",
    "tolerance",
    "passed",
    "score",
    "check_name",
    "checks",
    "expect_path",
    "answer_spec",
    "CheckResult",
)

FORBIDDEN_TEXTS = (
    "expected",
    "tolerance",
    "score",
    "expect/",
    "answer.toml",
    "fewer holes than expected",
)

TASK_VALUES = ("35214.602", "120.0", "60.0", "10.0", "-40.0", "40.0")

GEOMETRY = CandidateGeometry(
    is_valid=True,
    is_single_solid=True,
    volume=41237.5,
    bbox_size=(97.0, 43.0, 8.0),
    holes=(
        HoleSummary(diameter=6.0, x=-21.5, y=0.0),
        HoleSummary(diameter=6.0, x=0.0, y=12.5),
        HoleSummary(diameter=4.5, x=21.5, y=0.0),
    ),
)


def test_a_failed_build_is_rendered():
    """A failed build shows the status, the kind, the error and the traceback."""
    build = BuildFeedback(
        status="failed",
        failure_kind="syntax_error",
        error_text='File "plt9001_base.py", line 12\nSyntaxError: invalid syntax',
        traceback='Traceback (most recent call last):\n  File "plt9001_base.py", line 12',
    )

    text = feedback_text(build)

    assert "## Repair" in text
    assert "Build: failed (syntax_error)" in text
    assert "Error:" in text
    assert "SyntaxError: invalid syntax" in text
    assert "Traceback:" in text
    assert "Traceback (most recent call last):" in text
    assert "Candidate geometry" not in text


def test_a_successful_build_is_rendered():
    """A build that succeeded shows the status, the diagnostics, the findings
    and the geometry of the candidate."""
    build = BuildFeedback(status="ok")

    text = feedback_text(
        build,
        diagnostics=["the model rebuilt the shape"],
        conventions=["C2: the parameter block is missing"],
        geometry=GEOMETRY,
    )

    assert "Build: ok" in text
    assert "Diagnostics:" in text
    assert "the model rebuilt the shape" in text
    assert "Convention findings:" in text
    assert "C2: the parameter block is missing" in text
    assert "Candidate geometry (measured from the exported STEP):" in text
    assert "is_valid: true" in text
    assert "is_single_solid: true" in text
    assert "volume: 41237.5 mm^3" in text
    assert "bbox_size: 97.0 x 43.0 x 8.0 mm" in text
    assert "holes: 3" in text
    assert "hole 1: diameter 6.0 mm, position (-21.5, 0.0) mm" in text
    assert "hole 3: diameter 4.5 mm, position (21.5, 0.0) mm" in text


def test_the_sections_keep_their_order():
    """The sections come in the order the contract gives."""
    text = feedback_text(
        BuildFeedback(status="failed", failure_kind="runtime_error",
                      error_text="boom", traceback="Traceback"),
        diagnostics=["a diagnostic"],
        conventions=["C2: a finding"],
    )

    positions = [
        text.index("## Repair"),
        text.index("Build: failed (runtime_error)"),
        text.index("Error:"),
        text.index("Traceback:"),
        text.index("Diagnostics:"),
        text.index("Convention findings:"),
    ]

    assert positions == sorted(positions)


def test_the_geometry_is_left_out_when_the_build_failed():
    """A build that failed has no geometry to show."""
    text = feedback_text(
        BuildFeedback(status="failed", failure_kind="timeout"),
        geometry=GEOMETRY,
    )

    assert "Candidate geometry" not in text


def test_nothing_to_repair_is_an_empty_text():
    """A block with nothing to say is an empty text."""
    assert feedback_text(None) == ""
    assert feedback_text(BuildFeedback(status="")) == ""
    assert feedback_text(BuildFeedback(status="", failure_kind="",
                                       error_text="", traceback="")) == ""


def test_a_build_with_a_status_says_so():
    """A build that went well still says how it went."""
    text = feedback_text(BuildFeedback(status="ok"))

    assert "Build: ok" in text


def test_the_repair_instruction_is_always_there():
    """Every block carries the fixed repair instruction."""
    text = feedback_text(BuildFeedback(
        status="failed", failure_kind="timeout"))

    assert "replaced by the file you write now" in text
    assert "only the file" in text


def test_the_formatter_takes_candidate_side_inputs_only():
    """The formatter has four parameters and no evaluator parameter."""
    parameters = inspect.signature(feedback_text).parameters

    assert tuple(parameters) == (
        "build", "diagnostics", "conventions", "geometry")


@pytest.mark.parametrize("keyword", FORBIDDEN_KEYWORDS)
def test_the_formatter_refuses_an_evaluator_keyword(keyword):
    """An evaluator keyword is refused: there is no parameter for it."""
    arguments: dict[str, Any] = {keyword: "anything"}

    with pytest.raises(TypeError):
        feedback_text(None, **arguments)


def test_the_build_feedback_holds_no_evaluator_field():
    """The build feedback holds the outcome of the build and nothing else."""
    names = {field.name for field in fields(BuildFeedback)}

    assert names == {"status", "failure_kind", "error_text", "traceback"}
    for forbidden in FORBIDDEN_FIELDS:
        assert forbidden not in names


def test_the_rendered_feedback_carries_no_evaluator_text():
    """The rendered block of a built candidate names no evaluator value."""
    text = feedback_text(
        BuildFeedback(status="ok"),
        diagnostics=["the model rebuilt the shape"],
        conventions=["C2: the parameter block is missing"],
        geometry=GEOMETRY,
    )

    for forbidden in FORBIDDEN_TEXTS:
        assert forbidden not in text


def test_the_rendered_feedback_carries_no_expected_value_of_a_task():
    """No expected value of a committed task appears in the rendered block."""
    text = feedback_text(BuildFeedback(status="ok"), geometry=GEOMETRY)

    for value in TASK_VALUES:
        assert value not in text
