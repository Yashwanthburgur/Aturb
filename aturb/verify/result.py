"""One result type for every neutral check.

A check either measures a number and compares it with an expected number, or
it cannot be measured at all. Both cases end in the same result type, so a
caller can print, store and compare results without knowing which check
produced them.

The type holds no geometry and no CAD concept. It holds a name, a verdict, the
two numbers that were compared, the tolerance they were compared with and a
message. The numbers are plain floats in the unit of the file that was
measured.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    """The outcome of one neutral check.

    ``expected`` and ``actual`` are the two numbers the check compared, or
    ``None`` when the check could not be measured. ``tolerance`` is the
    distance the two numbers may differ by and still pass. ``message`` says
    why a check failed, and is empty when there is nothing to say.
    """

    name: str
    passed: bool
    expected: float | None
    actual: float | None
    tolerance: float
    message: str = ""

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict of this result."""
        return {
            "name": self.name,
            "passed": self.passed,
            "expected": self.expected,
            "actual": self.actual,
            "tolerance": self.tolerance,
            "message": self.message,
        }

    @classmethod
    def from_measurement(
        cls, name: str, expected: float, actual: float, tolerance: float
    ) -> "CheckResult":
        """Build a result from a measured number.

        The check passes when the measured number is within the tolerance of
        the expected one, so a difference of exactly the tolerance still
        passes. A negative tolerance can never be met, so such a check always
        fails.
        """
        passed = abs(actual - expected) <= tolerance
        return cls(
            name=name,
            passed=passed,
            expected=expected,
            actual=actual,
            tolerance=tolerance,
        )

    @classmethod
    def failure(cls, name: str, message: str) -> "CheckResult":
        """Build a result for a check that could not be measured.

        There are no numbers to report, so ``expected`` and ``actual`` are
        ``None`` and the tolerance is zero. The message says what went wrong.
        """
        return cls(
            name=name,
            passed=False,
            expected=None,
            actual=None,
            tolerance=0.0,
            message=message,
        )
