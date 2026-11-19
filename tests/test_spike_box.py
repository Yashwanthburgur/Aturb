"""FreeCAD test: build the spike box through the real runner and measure its STEP."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aturb.config import load_config
from aturb.contract.types import BuildRequest
from aturb.packs import default_packs_root, load_runner

REPO_ROOT = Path(__file__).resolve().parents[1]
BOX_PART = REPO_ROOT / "tools" / "spikes" / "parts" / "box_part.py"


def make_runner():
    """Load the production FreeCAD runner with the local config."""
    cfg = load_config(REPO_ROOT / "aturb.local.toml")
    return load_runner("freecad", cfg, default_packs_root())


@pytest.mark.freecad
def test_box_step_volume(tmp_path):
    """Build the spike box part and verify its STEP volume is 1000."""
    project = tmp_path / "proj"
    parts = project / "parts"
    parts.mkdir(parents=True)
    shutil.copyfile(BOX_PART, parts / "box0001_box.py")

    runner = make_runner()
    result = runner.build(BuildRequest(
        project_root=str(project),
        part_id="box0001",
        language=runner.info().language,
    ))

    assert result.status == "ok", result.error_text
    assert "step" in result.artifacts, "No STEP artifact in result"

    # Import STEP with build123d (only calls documented in docs/api_notes/build123d.md)
    from build123d import import_step

    solid = import_step(str(project / result.artifacts["step"]))

    # Assert volume is 1000 within 1e-6
    assert abs(solid.volume - 1000.0) <= 1e-6
