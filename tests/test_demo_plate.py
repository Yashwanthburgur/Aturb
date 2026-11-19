"""FreeCAD test: build the demo plate through the real runner and measure its STEP."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aturb.config import load_config
from aturb.contract.types import BuildRequest
from aturb.packs import default_packs_root, load_runner

REPO_ROOT = Path(__file__).resolve().parents[1]

# Hand calculation of the expected volume (plt0001_base_plate.py):
#
#   Plate volume = 120 x 60 x 5 = 36000 mm^3.
#   Two holes remove 2 x pi x 5^2 x 5 = 785.398 mm^3.
#   Expected volume = 35214.602 mm^3.


def make_runner():
    """Load the production FreeCAD runner with the local config."""
    cfg = load_config(REPO_ROOT / "aturb.local.toml")
    return load_runner("freecad", cfg, default_packs_root())


@pytest.mark.freecad
def test_demo_plate_geometry(tmp_path):
    """Build the PLT0001 base plate and verify its volume and bounding box."""
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

    # Import STEP with build123d (only calls documented in docs/api_notes/build123d.md)
    from build123d import import_step

    solid = import_step(str(project / result.artifacts["step"]))

    # Assert volume is 35214.602 within 0.01
    assert abs(solid.volume - 35214.602) <= 0.01

    # Assert bounding-box dimensions are 120 x 60 x 5 mm, each within 0.01
    size = solid.bounding_box().size
    assert abs(size.X - 120.0) <= 0.01
    assert abs(size.Y - 60.0) <= 0.01
    assert abs(size.Z - 5.0) <= 0.01
