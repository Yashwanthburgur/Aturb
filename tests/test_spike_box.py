"""FreeCAD test: build the spike box and measure its STEP volume with build123d."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fc_utils import run_spike_build


@pytest.mark.freecad
def test_box_step_volume(tmp_path):
    """Build the spike box part and verify its STEP volume is 1000."""
    repo_root = Path(__file__).resolve().parents[1]
    part_path = repo_root / "tools" / "spikes" / "parts" / "box_part.py"
    out_dir = tmp_path / "out"

    result = run_spike_build(part_path, out_dir)

    assert result["status"] == "ok", f"Build failed: {result.get('error', 'unknown')}"
    assert "step" in result, "No STEP artifact in result"

    # Import STEP with build123d (only calls documented in docs/api_notes/build123d.md)
    from build123d import import_step

    solid = import_step(result["step"])

    # Assert volume is 1000 within 1e-6
    assert abs(solid.volume - 1000.0) <= 1e-6
