"""Tests for the hole detection.

The committed fixture is a 120 x 60 x 5 plate with two 10 mm through-holes at
X = -40 and X = +40. The other models are written on the fly with build123d
calls that are recorded in docs/api_notes/build123d.md.
"""

from __future__ import annotations

from pathlib import Path

from build123d import Box, Cylinder, Location, export_step

from aturb.verify.holes import find_holes
from aturb.verify.step import load_step

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "packs" / "stub" / "fixtures" / "plate_2holes.step"

TOL = 0.01  # starting default


def _model(tmp_path: Path, shape, name: str = "part.step"):
    """Write a shape to a STEP file and read it back as a model."""
    path = tmp_path / name
    export_step(shape, str(path))
    return load_step(path)


def test_fixture_has_two_holes():
    """The plate fixture holds two holes."""
    holes = find_holes(load_step(FIXTURE_PATH))

    assert len(holes) == 2


def test_hole_diameter():
    """Both holes have diameter 10.0."""
    holes = find_holes(load_step(FIXTURE_PATH))

    assert all(abs(hole.diameter - 10.0) <= TOL for hole in holes)


def test_hole_position():
    """The holes sit at X = -40 and X = +40, on Y = 0 and Z = 0."""
    holes = find_holes(load_step(FIXTURE_PATH))

    for x in (-40.0, 40.0):
        matches = [hole for hole in holes if abs(hole.x - x) <= TOL]
        assert len(matches) == 1, f"expected one hole at X={x}"
        assert abs(matches[0].y) <= TOL
        assert abs(matches[0].z) <= TOL


def test_holes_are_through():
    """Both holes run through the plate."""
    holes = find_holes(load_step(FIXTURE_PATH))

    assert all(hole.through for hole in holes)


def test_holes_are_sorted_by_x():
    """The holes are reported from the lowest X to the highest."""
    holes = find_holes(load_step(FIXTURE_PATH))

    assert [round(hole.x, 3) for hole in holes] == [-40.0, 40.0]


def test_external_boss_is_not_a_hole(tmp_path):
    """A cylindrical boss is material, not a hole."""
    boss = Box(20, 20, 10) + Cylinder(3, 6).locate(Location((0, 0, 8)))

    assert find_holes(_model(tmp_path, boss)) == []


def test_blind_hole_is_not_through(tmp_path):
    """A blind hole is a hole, but it does not run through the part."""
    blind = Box(20, 20, 10) - Cylinder(3, 5).locate(Location((0, 0, 2.5)))

    holes = find_holes(_model(tmp_path, blind))

    assert len(holes) == 1
    assert abs(holes[0].diameter - 6.0) <= TOL
    assert not holes[0].through


def test_model_without_cylinders_has_no_holes(tmp_path):
    """A plain box has no hole."""
    assert find_holes(_model(tmp_path, Box(20, 20, 10))) == []


def test_tube_inner_wall_is_a_hole(tmp_path):
    """The inner wall of a tube is a hole, the outer wall is not."""
    tube = Cylinder(5, 20) - Cylinder(3, 20)

    holes = find_holes(_model(tmp_path, tube))

    assert len(holes) == 1
    assert abs(holes[0].diameter - 6.0) <= TOL
    assert holes[0].through


def test_plate_with_hole_and_boss_reports_only_the_hole(tmp_path):
    """A boss next to a hole does not add a second hole."""
    part = (
        Box(20, 20, 10)
        - Cylinder(3, 10)
        + Cylinder(2, 4).locate(Location((6, 0, 7)))
    )

    holes = find_holes(_model(tmp_path, part))

    assert len(holes) == 1
    assert abs(holes[0].diameter - 6.0) <= TOL
    assert holes[0].through


def test_stepped_hole_is_reported_as_two_cylinders(tmp_path):
    """A counterbore is two cylindrical faces, so it is two holes."""
    part = (
        Box(20, 20, 10)
        - Cylinder(5, 3).locate(Location((0, 0, 3.5)))
        - Cylinder(3, 7).locate(Location((0, 0, -1.5)))
    )

    holes = find_holes(_model(tmp_path, part))

    assert len(holes) == 2
    diameters = sorted(hole.diameter for hole in holes)
    assert abs(diameters[0] - 6.0) <= TOL
    assert abs(diameters[1] - 10.0) <= TOL
    assert all(hole.through for hole in holes)


def test_holes_that_cross_are_both_found(tmp_path):
    """Two holes that cross are both found and both run through."""
    part = (
        Box(20, 20, 10)
        - Cylinder(3, 10)
        - Cylinder(3, 10).locate(Location((4, 0, 0)))
    )

    holes = find_holes(_model(tmp_path, part))

    assert len(holes) == 2
    assert all(abs(hole.diameter - 6.0) <= TOL for hole in holes)
    assert all(hole.through for hole in holes)
