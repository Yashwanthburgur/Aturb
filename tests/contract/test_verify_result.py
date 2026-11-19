"""Tests for the neutral check result type.

A check either measures a number and compares it with an expected number, or
it cannot be measured at all. Both cases end in the same result type, so the
result can be printed, stored and compared without knowing which check made
it.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from aturb.verify.result import CheckResult


def test_a_measurement_inside_the_tolerance_passes():
    """A measured number within the tolerance of the expected one passes."""
    result = CheckResult.from_measurement("volume", 100.0, 100.05, 0.1)

    assert result.passed
    assert result.name == "volume"
    assert result.expected == 100.0
    assert result.actual == 100.05
    assert result.tolerance == 0.1


def test_a_measurement_exactly_on_the_tolerance_passes():
    """A difference of exactly the tolerance still passes."""
    result = CheckResult.from_measurement("volume", 100.0, 100.1, 0.1)

    assert result.passed


def test_a_measurement_outside_the_tolerance_fails():
    """A measured number beyond the tolerance of the expected one fails."""
    result = CheckResult.from_measurement("volume", 100.0, 100.2, 0.1)

    assert not result.passed
    assert result.expected == 100.0
    assert result.actual == 100.2
    assert result.tolerance == 0.1


def test_a_failure_carries_no_numbers():
    """A check that could not be measured reports no numbers."""
    result = CheckResult.failure("volume", "the file could not be read")

    assert not result.passed
    assert result.name == "volume"
    assert result.expected is None
    assert result.actual is None
    assert result.message == "the file could not be read"


def test_to_dict_returns_the_six_fields():
    """The dict holds the six fields of the result."""
    result = CheckResult.from_measurement("volume", 100.0, 100.05, 0.1)

    assert result.to_dict() == {
        "name": "volume",
        "passed": True,
        "expected": 100.0,
        "actual": 100.05,
        "tolerance": 0.1,
        "message": "",
    }


def test_to_dict_of_a_failure_holds_no_numbers():
    """The dict of a failure holds None for the two numbers."""
    result = CheckResult.failure("volume", "the file could not be read")

    assert result.to_dict() == {
        "name": "volume",
        "passed": False,
        "expected": None,
        "actual": None,
        "tolerance": 0.0,
        "message": "the file could not be read",
    }


def test_the_result_is_json_serializable():
    """The dict of a result can be stored as JSON."""
    result = CheckResult.from_measurement("volume", 100.0, 100.05, 0.1)

    loaded = json.loads(json.dumps(result.to_dict()))

    assert loaded["name"] == "volume"
    assert loaded["passed"] is True
    assert loaded["expected"] == 100.0
    assert loaded["actual"] == 100.05


def test_the_result_is_frozen():
    """A result cannot be changed once it is made."""
    result = CheckResult.from_measurement("volume", 100.0, 100.05, 0.1)

    with pytest.raises(FrozenInstanceError):
        result.passed = False
