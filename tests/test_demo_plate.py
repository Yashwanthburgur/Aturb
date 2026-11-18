"""FreeCAD test: build the demo plate and measure its STEP geometry with build123d."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fc_utils import run_spike_build

# Hand calculation of the expected volume (plt0001_base_plate.py):
#
#   Plate volume = 120 x 60 x 5 = 36000 mm^3.
#   Two holes remove 2 x pi x 5^2 x 5 = 785.398 mm^3.
#   Expected volume = 35214.602 mm^3.


@pytest.mark.freecad
def test_demo_plate_geometry(tmp_path):
    """Build the PLT0001 base plate and verify its volume and bounding box."""
    repo_root = Path(__file__).resolve().parents[1]
    part_path = repo_root / "projects" / "demo" / "parts" / "plt0001_base_plate.py"
    out_dir = tmp_path / "out"

    result = run_spike_build(part_path, out_dir)

    assert result["status"] == "ok", f"Build failed: {result.get('error', 'unknown')}"
    assert "step" in result, "No STEP artifact in result"

    # Import STEP with build123d (only calls documented in docs/api_notes/build123d.md)
    from build123d import import_step

    solid = import_step(result["step"])

    # Assert volume is 35214.602 within 0.01
    assert abs(solid.volume - 35214.602) <= 0.01

    # Assert bounding-box dimensions are 120 x 60 x 5 mm, each within 0.01
    size = solid.bounding_box().size
    assert abs(size.X - 120.0) <= 0.01
    assert abs(size.Y - 60.0) <= 0.01
    assert abs(size.Z - 5.0) <= 0.01
