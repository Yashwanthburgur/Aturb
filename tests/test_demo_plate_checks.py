"""The neutral checks of the demo plate, run over a real build.

The demo plate is built through the real runner, so the checks judge geometry
that a CAD produced. The checks themselves read only the exported STEP, so the
same checks judge the committed fixture in tests/test_verify_fixture_checks.py.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aturb.config import load_config
from aturb.contract.types import BuildRequest
from aturb.packs import default_packs_root, load_runner
from aturb.verify.expectations import checks_from_expectations, load_expectations
from aturb.verify.result import CheckResult
from aturb.verify.runner import hole_count_check, run_checks
from aturb.verify.step import StepModel, load_step

REPO_ROOT = Path(__file__).resolve().parents[1]


def make_runner():
    """Load the production runner with the local config."""
    cfg = load_config(REPO_ROOT / "aturb.local.toml")
    return load_runner("freecad", cfg, default_packs_root())


def demo_checks(model: StepModel, expect_path: Path) -> list[CheckResult]:
    """The neutral checks of the demo plate, read from an expectation file.

    The expected values give one result each. The hole count is also run
    through the check runner, so the runner is exercised on the same model.
    """
    expected = load_expectations(expect_path)
    results = checks_from_expectations(model, expected)
    results += run_checks(model, [hole_count_check(expected["hole_count"])])
    return results


@pytest.mark.freecad
def test_the_built_demo_plate_passes_every_check(tmp_path):
    """Build the demo plate through the real runner and check the exported STEP."""
    project = tmp_path / "proj"
    shutil.copytree(
        REPO_ROOT / "projects" / "demo",
        project,
        ignore=shutil.ignore_patterns("out"),
    )

    runner = make_runner()
    result = runner.build(BuildRequest(
        project_root=str(project),
        part_id="plt0001",
        language=runner.info().language,
    ))

    assert result.status == "ok", result.error_text
    assert "step" in result.artifacts, "No STEP artifact in result"

    model = load_step(project / result.artifacts["step"])
    results = demo_checks(model, project / "expect" / "plt0001.toml")

    assert results
    failed = [result for result in results if not result.passed]
    assert failed == [], [result.to_dict() for result in failed]
