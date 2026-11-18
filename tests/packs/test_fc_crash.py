"""End-to-end FreeCAD test: a harness that writes no result means runner_crash."""

from __future__ import annotations

from pathlib import Path

import pytest

from aturb.config import load_config
from aturb.contract.types import BuildRequest, FailureKind
from aturb.packs import default_packs_root, load_runner
from packs.freecad.runner import FreeCADRunner

REPO_ROOT = Path(__file__).resolve().parents[2]
HELLO_HARNESS = REPO_ROOT / "tools" / "spikes" / "fc_hello.py"


class HelloHarnessRunner(FreeCADRunner):
    """A runner whose harness prints a version and never writes a result."""

    def harness_path(self) -> Path:
        """Point at a harness that produces no result file."""
        return HELLO_HARNESS


@pytest.mark.freecad
def test_missing_result_file_is_runner_crash(tmp_path):
    """No result file from the harness is reported as RUNNER_CRASH."""
    cfg = load_config(REPO_ROOT / "aturb.local.toml")
    manifest = load_runner("freecad", cfg, default_packs_root())
    runner = HelloHarnessRunner(
        settings=manifest.settings, pack_dir=manifest.pack_dir)

    project = tmp_path / "proj"
    parts = project / "parts"
    parts.mkdir(parents=True)
    (parts / "plt0001_base_plate.py").write_text(
        "def build(doc):\n    return None\n", encoding="utf-8")

    request = BuildRequest(
        project_root=str(project), part_id="plt0001", language="python-freecad")
    result = runner.build(request)

    assert result.status == "failed"
    assert result.failure_kind is FailureKind.RUNNER_CRASH
    assert "no result file" in result.error_text
