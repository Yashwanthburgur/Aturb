"""Tests for the neutral STEP inspection module.

The fixture is the committed plate with two through-holes. Its expected values
come from the same hand calculation as tests/test_demo_plate.py:
120 x 60 x 5 = 36000 mm^3, minus 2 x pi x 5^2 x 5 = 785.398 mm^3.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aturb.verify.step import StepLoadError, StepModel, load_step

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "packs" / "stub" / "fixtures" / "plate_2holes.step"


def test_load_step_reads_the_fixture():
    """The committed fixture loads into a model that remembers its path."""
    model = load_step(FIXTURE_PATH)

    assert isinstance(model, StepModel)
    assert model.path == FIXTURE_PATH


def test_fixture_has_one_solid():
    """The plate fixture holds exactly one solid."""
    model = load_step(FIXTURE_PATH)

    assert len(model.solids) == 1


def test_fixture_volume():
    """The volume is 35214.602 mm^3 within 0.01."""
    model = load_step(FIXTURE_PATH)

    assert abs(model.volume - 35214.602) <= 0.01


def test_fixture_area():
    """The surface area is 16200 mm^2 within 0.01."""
    model = load_step(FIXTURE_PATH)

    assert abs(model.area - 16200.0) <= 0.01


def test_fixture_bbox_size():
    """The bounding box is 120 x 60 x 5 mm, each within 0.01."""
    model = load_step(FIXTURE_PATH)

    size = model.bbox_size
    assert abs(size.X - 120.0) <= 0.01
    assert abs(size.Y - 60.0) <= 0.01
    assert abs(size.Z - 5.0) <= 0.01


def test_fixture_is_valid():
    """The fixture is a valid solid."""
    model = load_step(FIXTURE_PATH)

    assert model.is_valid


def test_fixture_faces_and_edges():
    """The plate has 8 faces and 18 edges."""
    model = load_step(FIXTURE_PATH)

    assert len(model.faces) == 8
    assert len(model.edges) == 18


def test_missing_file_raises_step_load_error(tmp_path):
    """A missing file is reported as a StepLoadError."""
    with pytest.raises(StepLoadError):
        load_step(tmp_path / "absent.step")


def test_invalid_step_raises_step_load_error(tmp_path):
    """A file that is not a STEP is reported as a StepLoadError.

    The STEP reader also writes a parse error to stderr for this file. That
    message comes from the reader itself, so Python cannot capture it.
    """
    broken = tmp_path / "broken.step"
    broken.write_text("this is not a STEP file", encoding="utf-8")

    with pytest.raises(StepLoadError):
        load_step(broken)
