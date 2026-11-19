"""The neutral checks of the demo plate, run over the committed fixture.

The committed fixture is the same plate the demo project builds, so it must
pass every neutral check of the demo project. No CAD is involved: the checks
read the exported STEP and nothing else.

The same checks run over a real build in tests/test_demo_plate_checks.py.
"""

from __future__ import annotations

from pathlib import Path

from aturb.verify.expectations import checks_from_expectations, load_expectations
from aturb.verify.result import CheckResult
from aturb.verify.runner import hole_count_check, run_checks
from aturb.verify.step import StepModel, load_step

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECT_PATH = REPO_ROOT / "projects" / "demo" / "expect" / "plt0001.toml"
FIXTURE_PATH = REPO_ROOT / "packs" / "stub" / "fixtures" / "plate_2holes.step"


def demo_checks(model: StepModel, expect_path: Path) -> list[CheckResult]:
    """The neutral checks of the demo plate, read from an expectation file.

    The expected values give one result each. The hole count is also run
    through the check runner, so the runner is exercised on the same model.
    """
    expected = load_expectations(expect_path)
    results = checks_from_expectations(model, expected)
    results += run_checks(model, [hole_count_check(expected["hole_count"])])
    return results


def test_the_fixture_passes_every_demo_check():
    """Every neutral check of the demo plate passes on the committed fixture."""
    model = load_step(FIXTURE_PATH)

    results = demo_checks(model, EXPECT_PATH)

    assert results
    failed = [result for result in results if not result.passed]
    assert failed == [], [result.to_dict() for result in failed]
