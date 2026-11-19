"""Tests for a STEP file that holds several solids.

A STEP file may hold more than one solid. The model reports every solid it
holds, says plainly whether it holds exactly one, and measures the whole file
rather than only its first solid.
"""

from __future__ import annotations

from pathlib import Path

from build123d import Box, Compound, Location, export_step

from aturb.verify.step import StepModel, load_step

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "packs" / "stub" / "fixtures" / "plate_2holes.step"

TOL = 0.01  # starting default


def _box(x: float):
    """A 10 mm box whose centre sits at the given X."""
    return Box(10, 10, 10).locate(Location((x, 0, 0)))


def _two_solid_model(tmp_path: Path) -> StepModel:
    """Write two 10 mm boxes into one STEP file and read it back."""
    path = tmp_path / "two_solids.step"
    export_step(Compound([_box(0), _box(30)]), str(path))
    return load_step(path)


def test_a_multi_solid_file_holds_every_solid(tmp_path):
    """The model reports both solids of the file."""
    model = _two_solid_model(tmp_path)

    assert len(model.solids) == 2


def test_each_solid_keeps_its_own_volume(tmp_path):
    """Each solid of the file measures 1000 mm^3."""
    model = _two_solid_model(tmp_path)

    for solid in model.solids:
        assert abs(solid.volume - 1000.0) <= TOL


def test_a_multi_solid_file_is_not_a_single_solid(tmp_path):
    """A file with two solids is not a single-solid file."""
    model = _two_solid_model(tmp_path)

    assert not model.is_single_solid


def test_the_total_volume_covers_every_solid(tmp_path):
    """The total volume of the file is 2000 mm^3."""
    model = _two_solid_model(tmp_path)

    assert abs(model.volume - 2000.0) <= TOL


def test_the_faces_of_every_solid_are_reported(tmp_path):
    """The model measures the whole file, not only its first solid."""
    model = _two_solid_model(tmp_path)

    assert len(model.faces) == 12


def test_a_single_solid_file_says_so(tmp_path):
    """A file with one solid is a single-solid file."""
    path = tmp_path / "one_solid.step"
    export_step(_box(0), str(path))
    model = load_step(path)

    assert model.is_single_solid


def test_the_committed_fixture_is_a_single_solid():
    """The plate fixture holds one solid."""
    model = load_step(FIXTURE_PATH)

    assert model.is_single_solid
