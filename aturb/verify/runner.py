"""Run neutral checks over one STEP file and collect the results.

A check is a callable that takes a model and returns one result. The runner
calls the checks in order and returns the results in the same order, so a
caller can line a result up with the check that made it.

A check that raises is reported as a failure carrying the exception text, so
one broken check never hides the others. The runner reads only the exported
STEP through the model it is given; it never reads CAD-native diagnostics.

A check carries its own name in its ``__name__``, and the runner uses that
name when the check breaks and cannot report a result of its own.

The hole-count check lives here because the hole detection card left it for
this task. It is built with the expected count, because a check only ever
receives the model when it runs.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from aturb.verify.holes import find_holes
from aturb.verify.result import CheckResult
from aturb.verify.step import StepModel

Check = Callable[[StepModel], CheckResult]


def run_checks(model: StepModel, checks: Iterable[Check]) -> list[CheckResult]:
    """Run every check over the model and return the results in order.

    A check that raises is reported as a failure with the exception text, so
    the checks after it still run and still report.
    """
    results: list[CheckResult] = []
    for check in checks:
        try:
            results.append(check(model))
        except Exception as exc:
            results.append(CheckResult.failure(_check_name(check), _error_text(exc)))
    return results


def hole_count_check(expected: int) -> Check:
    """A check that the model holds the expected number of holes.

    The count is compared exactly, so the tolerance is zero. The expected
    count is given when the check is built, because a check only receives the
    model when it runs.
    """
    if not isinstance(expected, int):
        raise TypeError("the expected hole count must be an integer")
    if expected < 0:
        raise ValueError("the expected hole count cannot be negative")

    def check(model: StepModel) -> CheckResult:
        count = len(find_holes(model))
        return CheckResult.from_measurement(
            "hole_count", float(expected), float(count), 0.0
        )

    check.__name__ = "hole_count"
    return check


def _check_name(check: Check) -> str:
    """The name of a check, used when the check itself cannot report one.

    A plain function carries its own name. A callable object carries the name
    of its class.
    """
    name = getattr(check, "__name__", None)
    if isinstance(name, str) and name:
        return name
    return type(check).__name__


def _error_text(exc: Exception) -> str:
    """The text of an exception, or its kind when it carries no text."""
    return str(exc) or type(exc).__name__
